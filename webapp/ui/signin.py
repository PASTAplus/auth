import daiquiri
import fastapi
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


# UI routes


@router.get('/ui/signin')
async def signin(
    request: starlette.requests.Request,
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    return util.templates.TemplateResponse(
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


@router.get('/ui/signin/link')
async def signin_link(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    profile_row = udb.get_profile(token.urid)
    return util.templates.TemplateResponse(
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


@router.get('/ui/signin/reset')
async def signin_reset(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    return util.templates.TemplateResponse(
        'signin-reset-pw.html',
        {
            # Base
            'token': token,
            # 'avatar_url': util.get_profile_avatar_url(profile_row),
            #
            'request': request,
        },
    )


# Internal routes


@router.api_route('/signin/token', methods=['GET', 'POST'])
async def signin_token(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
):
    # Example query parameters for Google login:
    # {
    #     'cname': 'Roger M',
    #     'email': 'roger.dahl.unm@gmail.com',
    #     'idp': 'google',
    #     'idp_token': 'ya29.a0AcM612y-....',
    #     'sub': '106181686037612928633',
    #     'token': 'cm9nZXIuZGFobC51bm1...',
    #     'uid': '106181686037612928633',
    #     'urid': 'PASTA-ea1877bbdf1e49cea9761c09923fc738',
    # }
    urid = request.query_params.get('urid')
    profile_row = udb.get_profile(urid)
    token = pasta_jwt.PastaJwt(
        {
            'sub': urid,
            'groups': udb.get_group_membership_grid_set(profile_row),
            'cn': profile_row.full_name,
            'gn': profile_row.given_name,
            'sn': profile_row.family_name,
            'email': profile_row.email,
            # We don't have an email verification procedure yet
            # 'email_verified': True,
            'email_notifications': profile_row.email_notifications,
            'idp': request.query_params.get('idp'),
            'uid': request.query_params.get('uid'),
        }
    )
    response = starlette.responses.RedirectResponse(
        url=util.url('/ui/profile'),
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )
    response.set_cookie(key='token', value=token.encode())
    return response


@router.api_route('/signin/link/token', methods=['GET', 'POST'])
async def signin_token(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    profile_row = udb.get_profile(token.urid)
    # As with the signin_token route, we receive all of the IdP details as query params. But
    # since we're already logged in, we're not creating a new token. So we ignore all but
    # params we need for linking the account.
    idp_name = request.query_params.get('idp')
    uid = request.query_params.get('uid')
    udb.move_identity(idp_name, uid, profile_row)
    response = starlette.responses.RedirectResponse(
        url=util.url('/ui/profile'),
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )
    return response


@router.get('/signout')
async def signout(request: starlette.requests.Request):
    response = starlette.responses.RedirectResponse(
        url=util.url('/ui/signin'),
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )
    response.delete_cookie('token')
    return response
