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
    profile_row = udb.get_profile(token.urid)
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


@router.get('/dev/signin/{urid}')
@assert_dev_enabled
async def dev_signin_urid(
    urid: str,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
):
    response = util.redirect_internal('/ui/profile')
    profile_row = udb.get_profile(urid)
    pasta_token = pasta_jwt.PastaJwt(
        {
            'sub': urid,
            'groups': udb.get_group_membership_grid_set(profile_row),
        }
    )
    response.set_cookie(key='pasta_token', value=pasta_token)
    return response
