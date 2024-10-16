import daiquiri
import fastapi
import starlette.datastructures
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.iface
import pasta_jwt
import util

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


@router.get('/dev/token')
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
            #
            'request': request,
            'token_pp': token.claims_pp,
        },
    )

@router.get('/dev/profiles')
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
            #
            'request': request,
            'profile_list': profile_list,
        },
    )


@router.get('/dev/signin/{urid}')
async def dev_signin_urid(
    urid: str,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
):
    response = starlette.responses.RedirectResponse(
        url=util.url('/ui/profile'),
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )
    profile_row = udb.get_profile(urid)
    group_set = udb.get_group_membership_grid_set(profile_row)
    token = pasta_jwt.PastaJwt({'sub': urid, 'groups': group_set})
    response.set_cookie(key='token', value=token.encode())
    return response
