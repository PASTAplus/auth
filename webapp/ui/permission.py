import html
import re
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
import util.edi_token
import util.pretty
import util.url
import util.search_cache
import util.template
from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


PACKAGE_ID_RX = re.compile('^([a-zA-Z-]+).(\d+).(\d+)$')

#
# UI routes
#


@router.get('/ui/permission/search')
async def get_ui_permission_search(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Permissions Search page.
    - This page is opened when the user clicks on the "Permission" main menu.
    """
    return util.template.templates.TemplateResponse(
        'permission-search.html',
        {
            # Base
            'request': request,
            'profile': token_profile_row,
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row),
            'error_msg': request.query_params.get('error'),
            'info_msg': request.query_params.get('info'),
            # Page
            'package_scope_list': await dbi.get_search_package_scopes(),
            'resource_type_list': await dbi.get_search_resource_types(),
        },
    )


@router.get('/ui/permission/{search_uuid}')
async def get_ui_permission(
    search_uuid: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
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
        return util.url.internal(f'/ui/permission/search')

    root_count = await dbi.get_search_result_count(search_uuid)
    search_session_row = await dbi.get_search_session(search_uuid)
    search_type = search_session_row.search_params.get('search-type')
    if search_type == 'package-search':
        search_result_msg = f'Found {root_count} package{"s" if root_count != 1 else ""}'
    elif search_type == 'general-search':
        search_result_msg = f'Found {root_count} resource{"s" if root_count != 1 else ""}'
    else:
        raise ValueError(f"Unknown search-type: {search_type}")

    return util.template.templates.TemplateResponse(
        'permission.html',
        {
            # Base
            'request': request,
            'profile': token_profile_row,
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row),
            'error_msg': request.query_params.get('error'),
            'info_msg': request.query_params.get('info'),
            # Page
            'public_edi_id': Config.PUBLIC_EDI_ID,
            'authenticated_edi_id': Config.AUTHENTICATED_EDI_ID,
            'root_count': root_count,
            'search_uuid': search_uuid,
            'search_result_msg': search_result_msg,
        },
    )


#
# Landing pages
#

# https://auth-d.edirepository.org/auth/package?id=ecotrends.3.1&token=...
@router.get('/package')
async def get_package_landing_page(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
):
    """Package landing page that redirects to the permission search with package scope."""
    package_id = request.query_params.get('id')
    if m := PACKAGE_ID_RX.match(package_id):
        param_dict = {
            'search-type': 'package-search',
            'scope': m.group(1),
            'identifier': m.group(2),
            'revision': m.group(3),
        }
    else:
        return starlette.responses.Response(
            content=f'Invalid package ID: {html.escape(package_id, quote=True)}',
            status_code=starlette.status.HTTP_400_BAD_REQUEST,
        )
    token_str = request.query_params.get('token')
    edi_token = await util.edi_token.decode(dbi, token_str)
    if edi_token is None:
        return starlette.responses.Response(
            content='Invalid or expired token',
            status_code=starlette.status.HTTP_401_UNAUTHORIZED,
        )
    token_profile_row = await dbi.get_profile(edi_token.edi_id)
    new_search_session = await dbi.create_search_session(token_profile_row, param_dict)
    response = util.url.internal(f'/ui/permission/{new_search_session.uuid}')
    response.set_cookie('edi-token', token_str)
    return response


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
    return util.url.internal(f'/ui/permission/{new_search_session.uuid}')


@router.get('/int/api/permission/slice')
async def get_ui_api_permission_slice(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
):
    """Called when the permission search results panel is scrolled or first opened.
    Returns a slice of root resources for the current search session.
    """
    if request.state.claims is None:
        return starlette.responses.Response(status_code=starlette.status.HTTP_401_UNAUTHORIZED)
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


@router.get('/int/api/permission/tree/{root_id}')
async def get_ui_api_permission_tree(
    root_id: int,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Called when user clicks the expand button or checkbox in a root element.
    - This method takes a single root ID and returns a single tree with that root.
    """
    if request.state.claims is None:
        return starlette.responses.Response(status_code=starlette.status.HTTP_401_UNAUTHORIZED)
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
    return starlette.responses.JSONResponse(tree_dict)


@router.post('/int/api/permission/aggregate/get')
async def post_permission_aggregate_get(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Called when the user changes a resource check box in the resource tree."""
    if request.state.claims is None:
        return starlette.responses.Response(status_code=starlette.status.HTTP_401_UNAUTHORIZED)
    resource_list = await request.json()
    resource_generator = dbi.get_resource_filter_gen(
        token_profile_row, resource_list, db.models.permission.PermissionLevel.CHANGE
    )
    permission_list = await get_aggregate_permission_list(dbi, resource_generator)
    return starlette.responses.JSONResponse(permission_list)


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
                'avatar_url': await util.avatar.get_profile_avatar_url(dbi, profile_row),
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
                'avatar_url': util.avatar.get_group_avatar_url(),
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
            'description': public_row.email or '',
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, public_row),
        }

    return sorted(principal_dict.values(), key=db.resource_tree._get_principal_sort_key)


@router.post('/int/api/permission/principal/search')
async def post_permission_principal_search(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    # Prevent this from being called by anyone not logged in
    _token_profile_row: util.dependency.Profile = fastapi.Depends(
        util.dependency.token_profile_row
    ),
):
    """Called when user types in the principal search box."""
    if request.state.claims is None:
        return starlette.responses.Response(status_code=starlette.status.HTTP_401_UNAUTHORIZED)
    query_dict = await request.json()
    query_str = query_dict.get('query')
    principal_list = await util.search_cache.search(dbi, query_str)
    return starlette.responses.JSONResponse(principal_list)


@router.post('/int/api/permission/update')
async def post_permission_update(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Called when the user changes the permission level dropdown for a profile."""
    if request.state.claims is None:
        return starlette.responses.Response(status_code=starlette.status.HTTP_401_UNAUTHORIZED)
    # TODO: There is a race condition where changes can be lost if the user changes multiple times
    # quickly for the same profile. This probably happens because the change is asynchronously sent
    # to the server, and the list is then async updated while the old list still exists and is still
    # enabled in the UI. After fixing, the solution can be checked by adding a sleep on the server
    # side, or by setting a very low bandwidth limit in the browser dev tools.
    update_dict = await request.json()
    # changePermission level access on a resource cannot be removed if it's the last access at that
    # level.
    resource_list = update_dict['resources']
    permission_level = db.models.permission.permission_level_int_to_enum(
        update_dict['permissionLevel']
    )
    total_count = len(resource_list)
    if permission_level != db.models.permission.PermissionLevel.CHANGE:
        resource_list = [
            resource_id
            for resource_id in resource_list
            if await dbi.count_rules_by_resource(
                resource_id, db.models.permission.PermissionLevel.CHANGE
            )
            > 1
        ]
    await dbi.set_permissions(
        token_profile_row,
        resource_list,
        update_dict['principalId'],
        permission_level,
    )
    return starlette.responses.JSONResponse(
        {
            'total_count': total_count,
            'eligible_count': len(resource_list),
        }
    )
