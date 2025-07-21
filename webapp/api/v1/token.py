"""Token API v1: Manage EDI tokens
Docs:./docs/api/token.md
"""

import fastapi
import starlette.requests
import starlette.responses

import api.utils
import util.dependency
import util.exc
import util.pasta_jwt
import util.profile_cache
import util.url


import fastapi
import starlette.requests
import starlette.responses
import starlette.status

import util.old_token
import util.pasta_crypto
from config import Config

router = fastapi.APIRouter()

PUBLIC_KEY = util.pasta_crypto.import_key(Config.PASTA_TOKEN_PUBLIC_KEY_PATH)
PRIVATE_KEY = util.pasta_crypto.import_key(Config.PASTA_TOKEN_PRIVATE_KEY_PATH)


@router.post('/refresh')
async def post_refresh(
    request: starlette.requests.Request,
):
    """Validate and refresh an old style authentication token.

    A refreshed token is a token that matches the original token but has a new TTL.
    """
    external_token = (await request.body()).decode('utf-8')

    # Verify the token signature
    try:
        util.pasta_crypto.verify_auth_token(PUBLIC_KEY, external_token)
    except ValueError as e:
        raise fastapi.HTTPException(
            status_code=starlette.status.HTTP_401_UNAUTHORIZED,
            detail=f'Attempted to refresh invalid token: {e}',
        )

    # Verify the token TTL
    token_obj = util.old_token.OldToken()
    token_obj.from_auth_token(external_token)
    if not token_obj.is_valid_ttl():
        raise fastapi.HTTPException(
            status_code=starlette.status.HTTP_401_UNAUTHORIZED,
            detail=f'Attempted to refresh invalid token: Token has expired',
        )

    # Create the refreshed token
    token_obj = util.old_token.OldToken()
    token_obj.from_auth_token(external_token)
    token_obj.ttl = token_obj.new_ttl()

    response = starlette.responses.Response(
        content=util.pasta_crypto.create_auth_token(PRIVATE_KEY, token_obj.to_string()),
    )

    # In the Portal, the TokenRefreshFilter middleware activates immediately, on the login request
    # itself, so we have to set the cookie here.
    # response.set_cookie('auth-token', token_obj.to_string())

    return response


@router.post('/v1/token/{edi_id}')
async def post_token(
    edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
):
    """Create a new token for an existing profile.
    The token does not include the IdP information that is normally included in a token created via
    the login flow, as that information may not exist for the profile being accessed.
    """
    api_method = 'getToken'
    # Check that the request body is valid JSON
    try:
        request_dict = await api.utils.request_body_to_dict(request)
    except ValueError as e:
        return api.utils.get_response_400_bad_request(request, api_method, 'Invalid request')
    # Check that the request contains the required fields
    try:
        key = request_dict['key']
    except KeyError as e:
        return api.utils.get_response_400_bad_request(request, api_method, 'Invalid request')
    # Check the key
    if not (Config.TOKEN_KEY and key == Config.TOKEN_KEY):
        return api.utils.get_response_403_forbidden(
            request, api_method, 'Invalid request', edi_id=edi_id
        )
    # Check that the profile exists
    profile_row = await dbi.get_profile(edi_id)
    if not profile_row:
        return api.utils.get_response_404_not_found(
            request, api_method, 'Invalid request', edi_id=edi_id
        )
    edi_token = await create_edi_token(dbi, profile_row)
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Token created successfully',
        edi_id=edi_id,
        token=edi_token.encode(),
    )


async def create_edi_token(dbi, profile_row):
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
    return edi_token
