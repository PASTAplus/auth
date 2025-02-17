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
import util.avatar
import util.filesystem
import util.old_token
import util.pasta_crypto
import util.pasta_jwt
import util.pasta_ldap
import util.search_cache
import util.template
import util.utils

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
async def get_dev_token(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    if token is None:
        return util.template.templates.TemplateResponse(
            'token.html',
            {
                # Base
                'token': token,
                'avatar_url': util.avatar.get_anon_avatar_url(),
                'profile': None,
                #
                'request': request,
                'token_pp': 'NO TOKEN',
            },
        )
    profile_row = udb.get_profile(token.pasta_id)
    return util.template.templates.TemplateResponse(
        'token.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(profile_row),
            'profile': profile_row,
            #
            'request': request,
            'token_pp': token.claims_pp,
        },
    )


@router.get('/dev/profiles')
@assert_dev_enabled
async def get_dev_profiles(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    profile_list = udb.get_all_profiles()
    return util.template.templates.TemplateResponse(
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
async def get_dev_signin(
    idp_name: str,
    idp_uid: str,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
):
    response = util.utils.redirect_internal('/ui/profile')
    identity_row = udb.get_identity(idp_name, idp_uid)
    pasta_token = util.pasta_jwt.make_jwt(udb, identity_row, is_vetted=True)
    response.set_cookie(key='pasta_token', value=pasta_token)
    return response
