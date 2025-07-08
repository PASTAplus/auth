import fastapi
import psycopg.errors
import sqlalchemy.exc
import starlette.requests
import starlette.responses

import api.utils
import db.models.permission
import db.models.permission
import util.dependency
import util.exc
import util.pasta_jwt
import util.url

router = fastapi.APIRouter(prefix='/v1')


@router.post('/token/{edi_id}')
async def post_token(
    edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    # token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Create a new token for an existing profile.
    The token will be created with the identity that was last used to sign in.
    """
    if not edi_id:
        return starlette.responses.JSONResponse(
            status_code=400,
            content={'error': 'edi_id is required'},
        )

    identity_row = await dbi.get_identity_by_edi_id(edi_id)
    edi_token = await util.pasta_jwt.make_jwt(dbi, identity_row)

    return starlette.responses.JSONResponse(
        status_code=200,
        content={
            'token': edi_token,
        },
    )
