import daiquiri
import fastapi
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.iface
import jwt_token
import util
from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()
templates = starlette.templating.Jinja2Templates(Config.TEMPLATES_PATH)


@router.get('/signin')
async def signin(
    request: starlette.requests.Request,
    token: jwt_token.NewToken | None = fastapi.Depends(jwt_token.token),
):
    return templates.TemplateResponse(
        'signin.html',
        {
            # Base
            'token': token,
            #
            'request': request,
            'target_url': Config.SERVICE_BASE_URL + '/signin/token',
            'title': 'Sign in',
            'text': 'Select your identity provider to sign in.',
        },
    )


@router.api_route('/signin/token', methods=['GET', 'POST'])
async def signin_token(request: starlette.requests.Request):
    urid = request.query_params.get('urid')
    token = jwt_token.NewToken(urid=urid)
    response = starlette.responses.RedirectResponse(
        Config.SERVICE_BASE_URL + '/profile',
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )
    response.set_cookie(key='token', value=await token.as_json())
    return response

@router.api_route('/signin/link/token', methods=['GET', 'POST'])
async def signin_token(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: jwt_token.NewToken | None = fastapi.Depends(jwt_token.token),
):
    profile_row = udb.get_profile(token.urid)
    # urid = request.query_params.get('urid')
    # idp_token = request.query_params.get('idp_token')
    idp_name = request.query_params.get('idp')
    uid = request.query_params.get('uid')
    # email = request.query_params.get('email')
    # full_name = request.query_params.get('full_name')
    # avatar_url = request.query_params.get('avatar_url')
    # pasta_token = request.query_params.get('pasta_token')

    # token = jwt_token.NewToken(urid=urid)
    udb.move_identity(idp_name, uid, profile_row)

    response = starlette.responses.RedirectResponse(
        Config.SERVICE_BASE_URL + '/profile',
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )
    return response


@router.get('/signin/link')
async def signin_link(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: jwt_token.NewToken | None = fastapi.Depends(jwt_token.token),
):
    profile_row = udb.get_profile(token.urid)
    return templates.TemplateResponse(
        'signin.html',
        {
            # Base
            'token': token,
            'avatar_url': util.get_profile_avatar_url(profile_row),
            #
            'request': request,
            'target_url': Config.SERVICE_BASE_URL + '/signin/link/token',
            'title': 'Link Account',
            'text': """
            <p>
            Sign in to the account you wish to link to this profile.
            </p>
            <p>
            Linking accounts allows you to sign in with multiple identity providers.
            </p>
            <p>
            Go to the <a href='/identity'>Accounts</a> page to see the accounts that are
            already linked to this profile.
            </p>
            """,
        },
    )


@router.get('/signin/reset')
async def signin_reset(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: jwt_token.NewToken | None = fastapi.Depends(jwt_token.token),
):
    return templates.TemplateResponse(
        'signin-reset-pw.html',
        {
            # Base
            'token': token,
            # 'avatar_url': util.get_profile_avatar_url(profile_row),
            #
            'request': request,
        },
    )


@router.get('/signout')
async def signout(request: starlette.requests.Request):
    response = starlette.responses.RedirectResponse(
        Config.SERVICE_BASE_URL + '/signin',
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )
    response.delete_cookie('token')
    return response
