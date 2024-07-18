import fastapi
import starlette.requests
import starlette.responses

import pasta_crypto
import pasta_token as pasta_token_
from config import Config

router = fastapi.APIRouter()

PUBLIC_KEY = pasta_crypto.import_key(Config.PUBLIC_KEY_PATH)
PRIVATE_KEY = pasta_crypto.import_key(Config.PRIVATE_KEY_PATH)


@router.post('/auth/refresh')
async def refresh_token(external_token: str):
    """Validate and refresh an authentication token.

    A refreshed token is a token that matches the original token's uid and
    groups but has a new TTL.
    """
    # Verify the token signature
    try:
        pasta_crypto.verify_auth_token(PUBLIC_KEY, external_token)
    except ValueError as e:
        msg = f'Attempted to refresh invalid token: {e}'
        raise fastapi.HTTPException(status_code=401, detail=msg)

    # Verify the token TTL
    token_obj = pasta_token_.PastaToken()
    token_obj.from_auth_token(external_token)
    if not token_obj.is_valid_ttl():
        msg = f'Attempted to refresh invalid token: Token has expired'
        raise fastapi.HTTPException(status_code=401, detail=msg)

    # Create the refreshed token
    token_obj = pasta_token_.PastaToken()
    token_obj.from_auth_token(external_token)
    token_obj.ttl = token_obj.new_ttl()

    return starlette.responses.Response(
        content=pasta_crypto.create_auth_token(PRIVATE_KEY, token_obj.to_string()),
    )
