"""Token API v1: Manage EDI tokens
Docs:./docs/api/token.md
"""

import fastapi
import jwt
import sqlalchemy.exc
import starlette.requests
import starlette.status

import api.utils
import util.dependency
import util.exc
import util.old_token
import util.pasta_crypto
import util.edi_token
import util.profile_cache
import util.url
from config import Config

router = fastapi.APIRouter()

# For the old style PASTA token
PUBLIC_KEY_OBJ = util.pasta_crypto.import_key(Config.PASTA_TOKEN_PUBLIC_KEY_PATH)
PRIVATE_KEY_OBJ = util.pasta_crypto.import_key(Config.PASTA_TOKEN_PRIVATE_KEY_PATH)

# For the new JWT EDI token
PRIVATE_KEY_STR = Config.JWT_PRIVATE_KEY_PATH.read_text()
PUBLIC_KEY_STR = Config.JWT_PUBLIC_KEY_PATH.read_text()


@router.post('/refresh')
async def post_refresh(
    request: starlette.requests.Request,
):
    """Validate and refresh PASTA and EDI authentication tokens.

    A refreshed token is a token that matches the original token but has a new TTL.
    """
    api_method = 'refreshToken'
    # Check that the request body is valid JSON
    try:
        request_dict = await api.utils.request_body_to_dict(request)
    except ValueError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Invalid JSON in request body: {e}'
        )
    # Check that the request contains the required fields
    try:
        pasta_token = request_dict['pasta-token']
        edi_token = request_dict['edi-token']
    except KeyError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Missing field in JSON in request body: {e}'
        )
    # Verify the pasta-token signature
    try:
        util.pasta_crypto.verify_auth_token(PUBLIC_KEY_OBJ, pasta_token)
    except ValueError as e:
        return api.utils.get_response_401_unauthorized(
            request, api_method, f'Attempted to refresh invalid pasta-token: {e}'
        )
    # Deserialize the old pasta-token and start building the new pasta-token
    new_pasta_token = util.old_token.OldToken()
    new_pasta_token.from_auth_token(pasta_token)
    # Verify the pasta-token TTL
    if not new_pasta_token.is_valid_ttl():
        return api.utils.get_response_401_unauthorized(
            request, api_method, 'Attempted to refresh invalid token: Token has expired'
        )
    # Update the pasta-token TTL
    new_pasta_token.ttl = new_pasta_token.new_ttl()
    new_pasta_token = util.pasta_crypto.create_auth_token(
        PRIVATE_KEY_OBJ, new_pasta_token.to_string()
    )
    # Update the edi-token TTL. We consider the old style pasta token to be 'authoritative', so we
    # refresh the edi-token even if it has expired, as long as the old style token has not.
    edi_token_claims_dict = jwt.decode(
        edi_token,
        PUBLIC_KEY_STR,
        algorithms=[Config.JWT_ALGORITHM],
        options={'verify_exp': False},
    )
    new_edi_token = util.edi_token.create_by_claims(**edi_token_claims_dict)
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'PASTA and EDI tokens refreshed successfully',
        **{
            'pasta-token': new_pasta_token,
            'edi-token': new_edi_token,
        },
    )


# @router.post('/refresh')
# async def post_refresh(
#     request: starlette.requests.Request,
# ):
#     """Validate and refresh an old style authentication token.
#
#     A refreshed token is a token that matches the original token but has a new TTL.
#     """
#     external_token = (await request.body()).decode('utf-8')
#
#     # Verify the token signature
#     try:
#         util.pasta_crypto.verify_auth_token(PUBLIC_KEY, external_token)
#     except ValueError as e:
#         raise fastapi.HTTPException(
#             status_code=starlette.status.HTTP_401_UNAUTHORIZED,
#             detail=f'Attempted to refresh invalid token: {e}',
#         )
#
#     # Verify the token TTL
#     token_obj = util.old_token.OldToken()
#     token_obj.from_auth_token(external_token)
#     if not token_obj.is_valid_ttl():
#         raise fastapi.HTTPException(
#             status_code=starlette.status.HTTP_401_UNAUTHORIZED,
#             detail=f'Attempted to refresh invalid token: Token has expired',
#         )
#
#     # Create the refreshed token
#     token_obj = util.old_token.OldToken()
#     token_obj.from_auth_token(external_token)
#     token_obj.ttl = token_obj.new_ttl()
#
#     response = starlette.responses.Response(
#         content=util.pasta_crypto.create_auth_token(PRIVATE_KEY, token_obj.to_string()),
#     )
#
#     # In the Portal, the TokenRefreshFilter middleware activates immediately, on the login request
#     # itself, so we have to set the cookie here.
#     # response.set_cookie('auth-token', token_obj.to_string())
#
#     return response


@router.post('/v1/token/{edi_id}')
async def post_token(
    edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
):
    """Create a new token for an existing profile.
    - The token does not include the IdP information that is normally included in a token created
    via the login flow, as that information may not exist for the profile being accessed.
    """
    api_method = 'getToken'
    # Check that the request body is valid JSON
    try:
        request_dict = await api.utils.request_body_to_dict(request)
    except ValueError:
        return api.utils.get_response_400_bad_request(request, api_method, 'Invalid request')
    # Check that the request contains the required fields
    try:
        key = request_dict['key']
    except KeyError:
        return api.utils.get_response_400_bad_request(request, api_method, 'Invalid request')
    # Check the key
    if not (Config.TOKEN_KEY and key == Config.TOKEN_KEY):
        return api.utils.get_response_403_forbidden(
            request, api_method, 'Invalid request', edi_id=edi_id
        )
    # Check that the profile exists
    try:
        profile_row = await dbi.get_profile(edi_id)
    except sqlalchemy.exc.NoResultFound:
        return api.utils.get_response_404_not_found(
            request, api_method, 'Invalid request', edi_id=edi_id
        )
    edi_token = await util.edi_token.create_by_profile(dbi, profile_row)
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Token created successfully',
        edi_id=edi_id,
        token=edi_token,
    )
