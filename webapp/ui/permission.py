import daiquiri
import fastapi
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.resource_tree
import util.avatar
import util.dependency
import util.pasta_jwt
import util.search_cache
import util.template

import db.permission

from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


#
# UI routes
#


@router.get('/ui/permission')
async def get_ui_permission(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Permission page. The contents of the panels are loaded separately."""
    return util.template.templates.TemplateResponse(
        'permission.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            'profile': token_profile_row,
            'resource_type_list': await udb.get_resource_types(token_profile_row),
            # Page
            'request': request,
            'public_edi_id': Config.PUBLIC_EDI_ID,
            'authenticated_edi_id': Config.AUTHENTICATED_EDI_ID,
            'resource_type': request.query_params.get('type', ''),
        },
    )


#
# Internal routes
#


@router.post('/permission/resource/filter')
async def post_permission_resource_filter(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Called when user types in the resource search filter and when the page is first opened."""
    query_dict = await request.json()
    resource_query = await udb.get_resource_list(
        token_profile_row, query_dict.get('query'), query_dict.get('type') or None
    )
    resource_tree = db.resource_tree.get_resource_tree_for_ui(resource_query)
    # pprint.pp(resource_tree)
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'resources': resource_tree,
        }
    )


@router.post('/permission/aggregate/get')
async def post_permission_aggregate_get(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
):
    """Called when the user changes a resource check box in the resource tree."""
    resource_list = await request.json()
    permission_generator = udb.get_permission_generator(resource_list)
    permission_list = await get_aggregate_permission_list(udb, permission_generator)
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'permissionArray': permission_list,
        }
    )


async def get_aggregate_permission_list(udb, permission_generator):
    principal_dict = {}

    async for (
        resource_row,
        rule_row,
        principal_row,
        profile_row,
        group_row,
    ) in permission_generator:
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
            db.permission.get_permission_level_enum(rule_row.permission).value,
        )

    # If the query did not include the public user, add it
    if Config.PUBLIC_EDI_ID not in {p['edi_id'] for p in principal_dict.values()}:
        public_row = await udb.get_public_profile()
        principal_dict[(Config.PUBLIC_EDI_ID, 'profile')] = {
            'principal_id': (
                await udb.get_principal_by_subject(
                    public_row.id, db.permission.subject_type_string_to_enum('profile')
                )
            ).id,
            'principal_type': 'profile',
            'edi_id': public_row.edi_id,
            'title': public_row.common_name,
            'description': (public_row.email or ''),
            'avatar_url': public_row.avatar_url,
        }

    return sorted(principal_dict.values(), key=db.resource_tree._get_principal_sort_key)


@router.post('/permission/principal/search')
async def post_permission_principal_search(
    request: starlette.requests.Request,
    # udb: util.dependency.UserDb = fastapi.Depends(db.iface.udb),
    # Prevent this from being called by anyone not logged in
    _token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Called when user types in the principal search box."""
    query_dict = await request.json()
    query_str = query_dict.get('query')
    principal_list = await util.search_cache.search(query_str, include_groups=True)
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'principals': principal_list,
        }
    )


#
# Rule CRUD
#


@router.post('/permission/update')
async def post_permission_update(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Called when the user changes the permission level dropdown for a profile. """
    # TODO: There is a race condition where changes can be lost if the user changes multiple times
    # quickly for the same profile. This probably happens because the change is asynchronously sent
    # to the server, and the list is then async updated while the old list still exists and is still
    # enabled in the UI. After fixing, the solution can be checked by adding a sleep on the server
    # side, or by setting a very low bandwidth limit in the browser dev tools.
    update_dict = await request.json()
    try:
        await udb.set_permissions(
            token_profile_row,
            update_dict['resources'],
            update_dict['principalId'],
            update_dict['permissionLevel'],
        )
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
