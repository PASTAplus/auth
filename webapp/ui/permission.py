import json

import daiquiri
import fastapi
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import util.avatar
import util.dependency
import util.pasta_jwt
import util.search_cache
import util.template
from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


#
# UI routes
#


@router.get('/ui/permission')
async def get_ui_permission(
    request: starlette.requests.Request,
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    return util.template.templates.TemplateResponse(
        'permission.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            'profile': token_profile_row,
            #
            'request': request,
            'public_pasta_id': Config.PUBLIC_PASTA_ID,
        },
    )


#
# Internal routes
#


@router.post('/permission/resource/search')
async def post_permission_resource_search(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Called when user types in the resource search box."""
    query_dict = await request.json()
    collection_query = await udb.get_resource_list(token_profile_row, query_dict.get('query'))
    collection_dict = get_aggregate_collection_dict(collection_query)
    log.debug(json.dumps(collection_dict, indent=2))
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'collection_dict': collection_dict,
        }
    )


def get_aggregate_collection_dict(collection_query):
    """Get a dict of collections with nested resources and permissions. The permissions are
    aggregated by principal, and only the highest permission level is returned for each principal
    and resource type.

    :return: A dict of collections
        - Each collection contains a dict of resource types
        - Each resource type contains a dict of resources
        - Each resource contains a dict of profiles
        - Each principal contains the max permission level found for that principal in the resource
        type
    """
    # Dicts preserve insertion order, so the dict structure will mirror the order in the query. The
    # order will also carry over to the JSON output.
    collection_dict = {}

    for (
        collection_row,
        resource_row,
        permission_row,
        profile_row,
        group_row,
    ) in collection_query.yield_per(Config.DB_YIELD_ROWS):
        resource_dict = collection_dict.setdefault(
            collection_row.id,
            {
                'collection_label': collection_row.label,
                'collection_type': collection_row.type,
                'resource_dict': {},
            },
        )['resource_dict']

        if resource_row is None:
            continue

        permission_dict = resource_dict.setdefault(
            resource_row.type,
            {
                'resource_id_dict': {},
                'principal_dict': {},
            },
        )

        permission_dict['resource_id_dict'][resource_row.id] = resource_row.label

        if permission_row is None:
            continue

        principal_dict = permission_dict['principal_dict']

        if profile_row is not None:
            # Principal is a profile
            assert group_row is None, 'Profile and group cannot join on same row'
            d = {
                'principal_id': profile_row.id,
                'principal_type': 'profile',
                'pasta_id': profile_row.pasta_id,
                'title': profile_row.full_name,
                'description': profile_row.email,
            }
        elif group_row is not None:
            # Principal is a group
            assert profile_row is None, 'Profile and group cannot join on same row'
            d = {
                'principal_id': group_row.id,
                'principal_type': 'group',
                'pasta_id': group_row.pasta_id,
                'title': group_row.name,
                'description': group_row.description,
            }
        else:
            assert False, 'Unreachable'

        principal_info_dict = principal_dict.setdefault(
            (d['principal_id'], d['principal_type']), {**d, 'permission_level': 0}
        )

        principal_info_dict['permission_level'] = max(
            principal_info_dict['permission_level'], permission_row.level.value
        )

    # Iterate over principal_dict and convert to sorted lists
    for collection_id, collection_info_dict in collection_dict.items():
        for resource_type, resource_info_dict in collection_info_dict['resource_dict'].items():
            resource_info_dict['principal_list'] = sorted(
                resource_info_dict['principal_dict'].values(),
                key=get_principal_sort_key,
            )
            del resource_info_dict['principal_dict']

    return collection_dict


def get_principal_sort_key(principal_dict):
    p = principal_dict
    return (
        (
            p['principal_type'],
            p['title'],
            p['description'],
            p['principal_id'],
        )
        if p['pasta_id'] != Config.PUBLIC_PASTA_ID
        else ('',)
    )


@router.post('/permission/aggregate/get')
async def post_permission_aggregate_get(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
):
    resource_list = await request.json()
    # log.debug(json.dumps(resource_list, indent=2))
    permission_query = await udb.get_permission_list(resource_list)
    permission_list = await get_aggregate_permission_list(udb, permission_query)
    # log.debug(json.dumps(permission_list, indent=2))
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'permission_list': permission_list,
        }
    )


async def get_aggregate_permission_list(udb, permission_query):
    principal_dict = {}

    for (
        collection_row,
        resource_row,
        permission_row,
        profile_row,
        group_row,
    ) in permission_query.yield_per(Config.DB_YIELD_ROWS):
        if profile_row is not None:
            # Principal is a profile
            assert group_row is None, 'Profile and group cannot join on same row'
            d = {
                'principal_id': profile_row.id,
                'principal_type': 'profile',
                'pasta_id': profile_row.pasta_id,
                'title': profile_row.full_name,
                'description': profile_row.email,
                'avatar_url': profile_row.avatar_url,
            }
        elif group_row is not None:
            # Principal is a group
            assert profile_row is None, 'Profile and group cannot join on same row'
            d = {
                'principal_id': group_row.id,
                'principal_type': 'group',
                'pasta_id': group_row.pasta_id,
                'title': group_row.name,
                'description': (group_row.description or '')
                + f' (Owner: {group_row.profile.full_name})'.strip(),
                'avatar_url': str(util.avatar.get_group_avatar_url()),
            }
        else:
            assert False, 'Unreachable'

        principal_info_dict = principal_dict.setdefault(
            (d['principal_id'], d['principal_type']), {**d, 'permission_level': 0}
        )

        principal_info_dict['permission_level'] = max(
            principal_info_dict['permission_level'], permission_row.level.value
        )

    # If the query did not include the public user, add it
    if Config.PUBLIC_PASTA_ID not in {p['pasta_id'] for p in principal_dict.values()}:
        public_row = udb.get_public_profile()
        principal_dict[(Config.PUBLIC_PASTA_ID, 'profile')] = {
            'principal_id': public_row.id,
            'principal_type': 'profile',
            'pasta_id': public_row.pasta_id,
            'title': public_row.full_name,
            'description': (public_row.email or ''),
            'avatar_url': public_row.avatar_url,  # str(util.avatar.get_public_avatar_url()),
        }

    return sorted(principal_dict.values(), key=get_principal_sort_key)


@router.post('/permission/principal/search')
async def post_permission_principal_search(
    request: starlette.requests.Request,
    # udb: util.dependency.UserDb = fastapi.Depends(db.iface.udb),
    # Prevent this from being called by anyone not logged in
    # token: util.dependency.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    query_dict = await request.json()
    query_str = query_dict.get('query')
    principal_list = await util.search_cache.search(query_str, include_groups=True)
    log.debug(json.dumps(principal_list, indent=2))
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'principal_list': principal_list,
        }
    )


#
# Permission CRUD
#


@router.post('/permission/update')
async def post_permission_update(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Called when the user changes the permission level dropdown for a profile."""
    # TODO: There is a race condition where changes can be lost if the user changes multiple times
    # quickly for the same profile. This probably happens because the change is asynchronously sent
    # to the server, and the list is then async updated while the old list still exists and is still
    # enabled in in the UI.
    #
    # After fix, the solution can be checked by adding a sleep on the server side, or by setting a
    # very low bandwidth limit in the browser dev tools.
    update_dict = await request.json()
    try:
        await udb.set_permission_on_resource_list(
            token_profile_row,
            update_dict['resources'],
            update_dict['principalId'],
            update_dict['principalType'],
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
