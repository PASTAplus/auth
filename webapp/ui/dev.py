import functools

import daiquiri
import fastapi
import starlette.datastructures
import starlette.exceptions
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.models.profile
import util.avatar
import util.dependency
import util.edi_token
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


@router.get('/ui/api/dev/profiles')
@assert_dev_enabled
async def get_dev_profiles(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    profile_list = await dbi.get_all_profiles()
    return util.template.templates.TemplateResponse(
        'index.html',
        {
            # Base
            'request': request,
            'profile': token_profile_row,
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row),
            'error_msg': request.query_params.get('error'),
            'success_msg': request.query_params.get('success'),
            # Page
            'profile_list': profile_list,
        },
    )


@router.get('/ui/api/dev/signin/{idp_name}/{idp_uid}')
@assert_dev_enabled
async def get_dev_signin(
    idp_name: db.models.profile.IdpName,
    idp_uid: str,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
):
    response = util.redirect.internal('/ui/profile')
    identity_row = await dbi.get_profile(idp_name, idp_uid)
    edi_token = await util.edi_token.create(dbi, identity_row)
    response.set_cookie(key='edi-token', value=edi_token)
    return response
