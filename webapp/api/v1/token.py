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

router = fastapi.APIRouter(prefix='/v1')

# For the old style PASTA token
PUBLIC_KEY_OBJ = util.pasta_crypto.import_key(Config.PASTA_TOKEN_PUBLIC_KEY_PATH)
PRIVATE_KEY_OBJ = util.pasta_crypto.import_key(Config.PASTA_TOKEN_PRIVATE_KEY_PATH)

# For the new JWT EDI token
PRIVATE_KEY_STR = Config.JWT_PRIVATE_KEY_PATH.read_text()
PUBLIC_KEY_STR = Config.JWT_PUBLIC_KEY_PATH.read_text()


@router.post('/token/refresh')
async def post_refresh(
    request: starlette.requests.Request,
):
    """Validate and refresh PASTA and EDI authentication tokens.
    - A refreshed token matches the original token but has a new TTL.
    - We consider the EDI token to be 'authoritative', so we refresh the pasta-token even if it has
    expired, as long as the EDI token has not.
    - This method is optimized for high traffic. It works directly with the tokens and does not
    query the database, LDAP, or the OAuth2 IdPs.
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
    # Update the edi-token TTL
    try:
        edi_token_claims_dict = jwt.decode(
            edi_token,
            PUBLIC_KEY_STR,
            algorithms=[Config.JWT_ALGORITHM],
        )
        new_edi_token = util.edi_token.create_by_claims(**edi_token_claims_dict)
    except (jwt.PyJWTError, TypeError) as e:
        return api.utils.get_response_401_unauthorized(
            request, api_method, f'Attempted to refresh invalid edi-token: {e}'
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
    # Update the pasta-token TTL
    new_pasta_token.ttl = new_pasta_token.new_ttl()
    new_pasta_token = util.pasta_crypto.create_auth_token(
        PRIVATE_KEY_OBJ, new_pasta_token.to_string()
    )
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'PASTA and EDI tokens refreshed successfully',
        **{
            'pasta-token': new_pasta_token,
            'edi-token': new_edi_token,
        },
    )


@router.post('/token/key')
async def post_token_key(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
):
    """Create a token for an API key."""
    api_method = 'getTokenForKey'
    # Check that the request body is valid JSON
    try:
        request_dict = await api.utils.request_body_to_dict(request)
    except ValueError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Invalid JSON in request body: {e}'
        )
    # Check that the request contains the required fields
    try:
        key_id = request_dict['key-id']
    except KeyError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Missing field in JSON in request body: {e}'
        )
    # Validate the key and get the associated profile
    profile_row = await dbi.get_profile_by_key_id(key_id)
    if not profile_row:
        return api.utils.get_response_401_unauthorized(request, api_method, 'Invalid API key')
    # Create the EDI token
    edi_token = await util.edi_token.create(dbi, profile_row)
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Token created successfully',
        **{
            'edi-token': edi_token,
        },
    )


@router.post('/token/{edi_id}')
async def post_token(
    edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
):
    """Create a new token for an existing profile."""
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
    edi_token = await util.edi_token.create(dbi, profile_row)
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Token created successfully',
        edi_id=edi_id,
        **{
            'edi-token': edi_token,
        },
    )
