import time

import daiquiri
import fastapi
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.db_interface
import db.models.permission
import db.resource_tree
import util.avatar
import util.dependency
import util.exc
import util.pasta_jwt
import util.pretty
import util.redirect
import util.search_cache
import util.template
from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


#
# UI routes
#


@router.get('/ui/permission/search')
async def get_ui_permission_search(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Permissions Search page.
    - This page is opened when the user clicks on the "Permission" main menu.
    """
    return util.template.templates.TemplateResponse(
        'permission-search.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            'profile': token_profile_row,
            # Page
            'request': request,
            'package_scope_list': await dbi.get_search_package_scopes(),
            'resource_type_list': await dbi.get_search_resource_types(),
        },
    )


@router.get('/ui/permission/{search_uuid}')
async def get_ui_permission(
    search_uuid: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Main Permissions page. The contents of the panels are loaded separately."""

    try:
        await dbi.populate_search_session(token_profile_row, search_uuid)
        await dbi.flush()
    except (util.exc.SearchSessionNotFoundError, util.exc.SearchSessionPermissionError):
        # The following conditions may occur, in which case we redirect to the search page, where
        # the user can provide search parameters again:
        # - We delete search sessions after a certain time, so the given search session UUID may not
        # exist anymore.
        # - The user might have a valid search session UUID, but the session could belong to another
        # user (e.g., if they bookmarked the search page, then logged in to a different profile).
        return util.redirect.internal(f'/ui/permission/search')

    root_count = await dbi.get_search_result_count(search_uuid)
    search_session_row = await dbi.get_search_session(search_uuid)
    search_type = search_session_row.search_params.get('search-type')
    if search_type == 'package-search':
        search_result_msg = f'Found {root_count} packages'
    elif search_type == 'general-search':
        search_result_msg = f'Found {root_count} resources'
    else:
        raise ValueError(f"Unknown search-type: {search_type}")

    return util.template.templates.TemplateResponse(
        'permission.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            'profile': token_profile_row,
            # Page
            'request': request,
            'public_edi_id': Config.PUBLIC_EDI_ID,
            'authenticated_edi_id': Config.AUTHENTICATED_EDI_ID,
            'root_count': root_count,
            'search_uuid': search_uuid,
            'search_result_msg': search_result_msg,
        },
    )


#
# Internal routes
#


@router.post('/ui/api/permission/search')
async def post_ui_permission_search(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Permission Search API"""
    form_data = await request.form()
    new_search_session = await dbi.create_search_session(token_profile_row, dict(form_data))
    return util.redirect.internal(f'/ui/permission/{new_search_session.uuid}')


@router.get('/ui/api/permission/slice')
async def get_ui_api_permission_slice(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    # token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Called when the permission search results panel is scrolled or first opened.
    Returns a slice of root resources for the current search session.
    """
    query_dict = request.query_params
    search_uuid = query_dict.get('uuid')
    start_idx = int(query_dict['start'])
    limit = int(query_dict['limit'])
    root_list = [
        {
            'id': root.id,
            'resource_id': root.resource_id,
            'label': root.resource_label,
            'type': root.resource_type,
        }
        for root in await dbi.get_search_result_slice(search_uuid, start_idx, limit)
    ]
    return starlette.responses.JSONResponse(root_list)


@router.get('/ui/api/permission/tree/{root_id}')
async def get_ui_api_permission_tree(
    root_id: int,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Called when user clicks the expand button or checkbox in a root element.
    - This method takes a single root ID and returns a single tree with that root.
    """
    resource_id_set = await dbi.get_resource_descendants_id_set([root_id])
    resource_generator = dbi.get_resource_filter_gen(
        token_profile_row, resource_id_set, db.models.permission.PermissionLevel.CHANGE
    )
    row_list = [row async for row in resource_generator]
    # If the root resource is not visible to the user, return None
    if root_id not in (row[0].id for row in row_list):
        tree_dict = None
    else:
        tree_dict = db.resource_tree.get_resource_tree_for_ui(row_list)[0]
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'tree': tree_dict,
        }
    )


@router.post('/ui/api/permission/aggregate/get')
async def post_permission_aggregate_get(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Called when the user changes a resource check box in the resource tree."""
    resource_list = await request.json()
    resource_generator = dbi.get_resource_filter_gen(
        token_profile_row, resource_list, db.models.permission.PermissionLevel.CHANGE
    )
    permission_list = await get_aggregate_permission_list(dbi, resource_generator)
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'permissionArray': permission_list,
        }
    )


async def get_aggregate_permission_list(dbi, resource_generator):
    principal_dict = {}

    async for (
        resource_row,
        rule_row,
        principal_row,
        profile_row,
        group_row,
    ) in resource_generator:
        if profile_row is not None:
            # Principal is a profile
            assert group_row is None, 'Profile and group cannot join on same row'
            d = {
                'principal_id': principal_row.id,
                'principal_type': 'profile',
                'edi_id': profile_row.edi_id,
                'title': profile_row.common_name,
                'description': profile_row.email,
                'avatar_url': profile_row.avatar_url,
            }
        elif group_row is not None:
            # Principal is a group
            assert profile_row is None, 'Profile and group cannot join on same row'
            d = {
                'principal_id': principal_row.id,
                'principal_type': 'group',
                'edi_id': group_row.edi_id,
                'title': group_row.name,
                'description': (group_row.description or ''),
                'avatar_url': str(util.avatar.get_group_avatar_url()),
            }
        else:
            assert False, 'Unreachable'

        principal_info_dict = principal_dict.setdefault(
            (d['principal_id'], d['principal_type']), {**d, 'permission_level': 0}
        )

        principal_info_dict['permission_level'] = max(
            principal_info_dict['permission_level'],
            db.models.permission.get_permission_level_enum(rule_row.permission).value,
        )

    # If the query did not include the public user, add it
    if Config.PUBLIC_EDI_ID not in {p['edi_id'] for p in principal_dict.values()}:
        public_row = await dbi.get_public_profile()
        principal_dict[(Config.PUBLIC_EDI_ID, 'profile')] = {
            'principal_id': (
                await dbi.get_principal_by_subject(
                    public_row.id, db.models.permission.subject_type_string_to_enum('profile')
                )
            ).id,
            'principal_type': 'profile',
            'edi_id': public_row.edi_id,
            'title': public_row.common_name,
            'description': (public_row.email or ''),
            'avatar_url': public_row.avatar_url,
        }

    return sorted(principal_dict.values(), key=db.resource_tree._get_principal_sort_key)


@router.post('/ui/api/permission/principal/search')
async def post_permission_principal_search(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    # Prevent this from being called by anyone not logged in
    _token_profile_row: util.dependency.Profile = fastapi.Depends(
        util.dependency.token_profile_row
    ),
):
    """Called when user types in the principal search box."""
    query_dict = await request.json()
    query_str = query_dict.get('query')
    principal_list = await util.search_cache.search(dbi, query_str, include_groups=True)
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'principals': principal_list,
        }
    )


@router.post('/ui/api/permission/update')
async def post_permission_update(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Called when the user changes the permission level dropdown for a profile."""
    # TODO: There is a race condition where changes can be lost if the user changes multiple times
    # quickly for the same profile. This probably happens because the change is asynchronously sent
    # to the server, and the list is then async updated while the old list still exists and is still
    # enabled in the UI. After fixing, the solution can be checked by adding a sleep on the server
    # side, or by setting a very low bandwidth limit in the browser dev tools.
    update_dict = await request.json()
    try:
        start_ts = time.time()
        await dbi.set_permissions(
            token_profile_row,
            update_dict['resources'],
            update_dict['principalId'],
            update_dict['permissionLevel'],
        )
        log.info('set_permissions(): %.3f sec', time.time() - start_ts)

    except ValueError as e:
        return starlette.responses.JSONResponse(
            {'status': 'error', 'message': str(e)},
            status_code=starlette.status.HTTP_400_BAD_REQUEST,
        )
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
        }
    )
