import fastapi
import starlette.requests
import starlette.responses

import api.utils
import util.dependency
import util.exc
import util.pasta_jwt
import util.profile_cache
import util.url

router = fastapi.APIRouter(prefix='/v1')


@router.post('/token/{edi_id}')
async def post_token(
    edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Superuser API to create a new token for an existing profile.

    For API access on behalf of any user profile, any authenticated user in the
    Config.SUPERUSER_LIST, can call this endpoint to receive a valid token that can then be used in
    API requests. The token can also be used to access the UI via a browser as that user.

    The token does not include the IdP information that is normally included in a token created
    via the login flow, as that information may not exist for the profile being accessed.
    """
    api_method = 'createToken'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that token belongs to a superuser
    if not util.profile_cache.is_superuser(token_profile_row):
        return api.utils.get_response_403_forbidden(None, api_method, 'Must be a superuser')
    # Check that the profile exists
    profile_row = await dbi.get_profile(edi_id)
    if not profile_row:
        return api.utils.get_response_404_not_found(
            request, api_method, 'Profile does not exist', edi_id=edi_id
        )
    # Create token
    principals_set = await dbi.get_equivalent_principal_edi_id_set(profile_row)
    principals_set.remove(profile_row.edi_id)
    edi_token = util.pasta_jwt.PastaJwt(
        {
            'sub': profile_row.edi_id,
            'cn': profile_row.common_name,
            'email': profile_row.email,
            'principals': principals_set,
            'isEmailEnabled': profile_row.email_notifications,
            'isEmailVerified': False,
            'identityId': -1,
            'idpName': 'Unknown',
            'idpUid': 'Unknown',
            'idpCname': 'Unknown',
        }
    )
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Token created successfully',
        edi_id=edi_id,
        token=edi_token.encode(),
    )
