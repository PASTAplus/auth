import functools

import daiquiri
import fastapi
import starlette.datastructures
import starlette.exceptions
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.models.identity
import util.avatar
import util.dependency
import util.pasta_jwt
import util.redirect
import util.template
from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


def assert_dev_enabled(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if not Config.ENABLE_DEV_MENU:
            raise starlette.exceptions.HTTPException(status_code=403, detail='Dev menu is disabled')
        return await func(*args, **kwargs)

    return wrapper


@router.get('/dev/profiles')
@assert_dev_enabled
async def get_dev_profiles(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
):
    profile_list = await dbi.get_all_profiles()
    return util.template.templates.TemplateResponse(
        'index.html',
        {
            # Base
            'token': token,
            'profile': None,
            # Page
            'request': request,
            'profile_list': profile_list,
        },
    )


@router.get('/dev/signin/{idp_name}/{idp_uid}')
@assert_dev_enabled
async def get_dev_signin(
    idp_name: db.models.identity.IdpName,
    idp_uid: str,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
):
    response = util.redirect.internal('/ui/profile')
    identity_row = await dbi.get_identity(idp_name, idp_uid)
    edi_token = await util.pasta_jwt.make_jwt(dbi, identity_row)
    response.set_cookie(key='edi-token', value=edi_token)
    return response
