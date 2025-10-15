"""Search API v1
Docs:./docs/api/profile.md
"""

import fastapi
import starlette.requests
import starlette.responses

import api.utils
import util.avatar
import util.dependency
import util.edi_token
import util.exc
import util.search_cache
import util.url

router = fastapi.APIRouter(prefix='/v1')


@router.get('/search')
async def get_v1_search(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """searchPrincipals():Search for EDI profiles and groups based on a provided search string."""
    api_method = 'searchPrincipals'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that the request contains the required fields
    try:
        search_str = request.query_params['s']
    except KeyError:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Invalid URL: Missing query parameter: s (search string)'
        )
    try:
        include_profiles = util.url.is_true(request.query_params.get('profiles', 'true'))
        include_groups = util.url.is_true(request.query_params.get('groups', 'true'))
    except ValueError as e:
        return api.utils.get_response_400_bad_request(request, api_method, f'Invalid URL: {e}')
    if not include_profiles and not include_groups:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Invalid URL: Must include profiles and/or groups'
        )

    profile_list = []
    group_list = []

    for d in await util.search_cache.search(dbi, search_str, include_profiles, include_groups):
        if d['principal_type'] == 'profile':
            profile_list.append(
                {
                    'edi_id': d['edi_id'],
                    'common_name': d['title'],
                    'email': d['description'],
                    'avatar_url': d['avatar_url'],
                }
            )
        elif d['principal_type'] == 'group':
            group_list.append(
                {
                    'edi_id': d['edi_id'],
                    'name': d['title'],
                    'description': d['description'],
                    'avatar_url': d['avatar_url'],
                }
            )
        else:
            assert False, 'Unreachable'

    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Profiles and/or groups searched successfully',
        profiles=profile_list,
        groups=group_list,
    )
