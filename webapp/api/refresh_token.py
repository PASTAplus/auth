import fastapi
import starlette.requests
import starlette.responses
import starlette.status

import old_token
import pasta_crypto
from config import Config

router = fastapi.APIRouter()

PUBLIC_KEY = pasta_crypto.import_key(Config.PUBLIC_KEY_PATH)
PRIVATE_KEY = pasta_crypto.import_key(Config.PRIVATE_KEY_PATH)


# @router.post('/v1/refresh')
@router.post('/refresh')
async def refresh_token(
    request: starlette.requests.Request,
):
    """Validate and refresh an old style authentication token.

    A refreshed token is a token that matches the original token's uid and
    groups but has a new TTL.
    """
    external_token = (await request.body()).decode('utf-8')

    # Verify the token signature
    try:
        pasta_crypto.verify_auth_token(PUBLIC_KEY, external_token)
    except ValueError as e:
        raise fastapi.HTTPException(
            status_code=starlette.status.HTTP_401_UNAUTHORIZED,
            detail=f'Attempted to refresh invalid token: {e}',
        )

    # Verify the token TTL
    token_obj = old_token.OldToken()
    token_obj.from_auth_token(external_token)
    if not token_obj.is_valid_ttl():
        raise fastapi.HTTPException(
            status_code=starlette.status.HTTP_401_UNAUTHORIZED,
            detail=f'Attempted to refresh invalid token: Token has expired',
        )

    # Create the refreshed token
    token_obj = old_token.OldToken()
    token_obj.from_auth_token(external_token)
    token_obj.ttl = token_obj.new_ttl()

    response = starlette.responses.Response(
        content=pasta_crypto.create_auth_token(PRIVATE_KEY, token_obj.to_string()),
    )

    # # In the Portal, the TokenRefreshFilter middleware activates immediately, on the login request
    # # itself, so we have to set the cookie here.
    # response.set_cookie('auth-token', token_obj.to_string())

    return response
