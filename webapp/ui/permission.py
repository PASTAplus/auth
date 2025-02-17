import json

import daiquiri
import fastapi
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.iface
import util.avatar
import util.filesystem
import util.old_token
import util.pasta_crypto
import util.pasta_jwt
import util.pasta_ldap
import util.search_cache
import util.template
import util.utils

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


# UI routes


@router.get('/ui/permission')
async def get_ui_permission(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    profile_row = udb.get_profile(token.pasta_id)
    return util.template.templates.TemplateResponse(
        'permission.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(profile_row),
            'profile': profile_row,
            #
            'request': request,
        },
    )


# Internal routes


@router.post('/permission/resource/search')
async def post_permission_resource_search(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    # token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    """Called when user types in the resource search box.
    """
    query_dict = await request.json()
    # profile_row = udb.get_profile(token.pasta_id)
    # permission_row = udb.get_permission(profile_row, form_data.get('permission-id'))
    # query_str = query_dict.get('query')
    # match_list = await fuzz.search(query_str)
    # candidate_list = udb.get_profiles_by_ids(match_list)
    profile_row = None  # udb.get_profile(token.pasta_id)
    # collection_list = udb.get_collection_list(profile_row, query_dict.get('query'))
    # client_collection_list = await get_client_collection_list(collection_list)
    client_collection_dict = await udb.get_aggregate_collection_dict(
        profile_row, query_dict.get('query')
    )
    log.debug(json.dumps(client_collection_dict, indent=2))
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'collection_dict': client_collection_dict,
        }
    )


@router.post('/permission/get-list')
async def post_permission_get_list(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    # token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    resource_list = await request.json()
    log.debug('1'*100)
    log.debug(json.dumps(resource_list, indent=2))
    profile_permission_list = await udb.get_aggregate_profile_permission_list(resource_list)
    log.debug(json.dumps(profile_permission_list, indent=2))
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'profile_permission_list': profile_permission_list,
        }
    )


async def get_client_permission_list(permission_list):
    """Create a set of plain key/value dicts with limited profile values for exposing
    client side."""
    return [
        {
            'permission_id': p.id,
            'level': p.permission_level.value,
            # Profile
            'profile_id': p.profile.id,
            'pasta_id': p.profile.pasta_id,
            'full_name': p.profile.full_name,
            'email': p.profile.email,
            'organization': p.profile.organization,
            'association': p.profile.association,
            'avatar_url': p.profile.avatar_url,
        }
        for p in permission_list
    ]


@router.post('/permission/candidate/search')
async def post_permission_candidate_search(
    request: starlette.requests.Request,
    # udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    # Prevent this from being called by anyone not logged in
    # token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    query_dict = await request.json()
    # profile_row = udb.get_profile(token.pasta_id)
    # permission_row = udb.get_permission(profile_row, form_data.get('permission-id'))
    query_str = query_dict.get('query')
    match_list = await util.search_cache.search(query_str)
    # candidate_list = udb.get_profiles_by_ids(match_list)
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            # 'candidate_list': await get_client_candidate_list(candidate_list),
            'candidate_list': match_list,
        }
    )


async def get_client_candidate_list(candidate_list):
    """Create a set of JSON serializable key/value dicts with limited profile values for
    exposing client side.
    """
    return [
        {
            'profile_id': p.id,
            'pasta_id': p.pasta_id,
            'full_name': p.full_name,
            'email': p.email,
            'organization': p.organization,
            'association': p.association,
            'avatar_url': p.avatar_url,
        }
        for p in candidate_list
    ]


#
# Permission CRUD
#


@router.post('/permission/update')
async def permission_update(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    """Called when the user changes the permission level dropdown for a profile."""

    # TODO: There is a race condition where changes can be lost if the user changes multiple times
    # quickly for the same profile. This probably happens because the change is asynchronously sent
    # to the server, and the list is then async updated while the old list still exists and is still
    # enabled in in the UI.
    #
    # After fix, the solution can be checked by adding a sleep on the server side, or by setting a
    # very low bandwidth limit in the browser dev tools.

    # TODO: Check if the user has permission to update the permission
    update_dict = await request.json()
    profile_row = udb.get_profile(token.pasta_id)
    try:
        await udb.update_permission(
            profile_row,
            update_dict['resources'],
            update_dict['profileId'],
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


# @router.post('/permission/crud')
# async def permission_crud(
#     request: starlette.requests.Request,
#     udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
#     token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
# ):
#     # TODO: Check if the user has permission to update the permission
#     param_dict = await request.json()
#     action = param_dict['action']
#     ret_dict = {}
#     try:
#         if action == 'create':
#             permission_row = await permission_create(udb, param_dict)
#             ret_dict['permissionId'] = permission_row.id
#         # elif action == 'update':
#         #     await permission_update(udb, param_dict)
#         # elif action == 'delete':
#         #     await permission_delete(udb, param_dict)
#         else:
#             raise ValueError('Invalid action')
#     except ValueError as e:
#         return starlette.responses.JSONResponse(
#             {'status': 'error', 'message': str(e)},
#             status_code=starlette.status.HTTP_400_BAD_REQUEST,
#         )
#     return starlette.responses.JSONResponse(
#         {
#             'status': 'ok',
#             **ret_dict,
#         },
#         status_code=starlette.status.HTTP_200_OK,
#     )
#
#
# async def permission_create(udb, param_dict):
#     return udb.create_permission(param_dict['resourceId'], param_dict['profileId'])
#
#
# async def permission_delete(udb, param_dict):
#     pass
