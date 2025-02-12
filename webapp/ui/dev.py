import functools

import daiquiri
import fastapi
import starlette.datastructures
import starlette.exceptions
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.iface
import pasta_jwt
import util
from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


def assert_dev_enabled(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if not Config.ENABLE_DEV_MENU:
            raise starlette.exceptions.HTTPException(
                status_code=403, detail='Dev menu is disabled'
            )
        return await func(*args, **kwargs)

    return wrapper


@router.get('/dev/token')
@assert_dev_enabled
async def dev_token(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    if token is None:
        return util.templates.TemplateResponse(
            'token.html',
            {
                # Base
                'token': token,
                'avatar_url': util.get_anon_avatar_url(),
                'profile': None,
                #
                'request': request,
                'token_pp': 'NO TOKEN',
            },
        )
    profile_row = udb.get_profile(token.pasta_id)
    return util.templates.TemplateResponse(
        'token.html',
        {
            # Base
            'token': token,
            'avatar_url': util.get_profile_avatar_url(profile_row),
            'profile': profile_row,
            #
            'request': request,
            'token_pp': token.claims_pp,
        },
    )


@router.get('/dev/profiles')
@assert_dev_enabled
async def index(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    profile_list = udb.get_all_profiles()
    return util.templates.TemplateResponse(
        'index.html',
        {
            # Base
            'token': token,
            'profile': None,
            #
            'request': request,
            'profile_list': profile_list,
        },
    )


@router.get('/dev/signin/{idp_name}/{idp_uid}')
@assert_dev_enabled
async def dev_signin_pasta_id(
    idp_name: str,
    idp_uid: str,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
):
    response = util.redirect_internal('/ui/profile')
    identity_row = udb.get_identity(idp_name, idp_uid)
    pasta_token = pasta_jwt.make_jwt(udb, identity_row, is_vetted=True)
    response.set_cookie(key='pasta_token', value=pasta_token)
    return response
