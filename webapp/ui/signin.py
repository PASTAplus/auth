import daiquiri
import fastapi
import starlette.requests
import starlette.templating
import starlette.responses
import starlette.datastructures
import starlette.status

import db.iface
import pasta_jwt
import pasta_ldap
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
    if token:
        return util.redirect_internal('/ui/profile')
    return util.templates.TemplateResponse(
        'signin.html',
        {
            # Base
            'token': None,
            'profile': None,
            #
            'request': request,
            'login_type': 'client',
            'target_url': Config.SERVICE_BASE_URL + '/ui/profile',
            'title': 'Sign in',
            'text': 'Select your identity provider to sign in.',
            'error': request.query_params.get('error'),
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
            'profile': None,
            #
            'request': request,
            'login_type': 'link',
            'target_url': Config.SERVICE_BASE_URL + '/ui/identity',
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
            'profile': None,
            # 'avatar_url': util.get_profile_avatar_url(profile_row),
            #
            'request': request,
        },
    )


#
# Internal routes
#


@router.post('/signin/ldap')
async def signin_ldap(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
):
    """Handle LDAP sign in from the Auth sign in page. This duplicates some of the logic
    in idp/ldap.py, but interacts with the browser instead of a server side client.
    """
    form_data = await request.form()
    login_type = form_data.get('login_type')
    username = form_data.get('username')
    password = form_data.get('password')
    ldap_dn = util.get_ldap_dn(username)

    if not pasta_ldap.bind(ldap_dn, password):
        return util.redirect_internal(
            '/ui/signin', error='Sign in failed. Please try again.'
        )

    log.debug(f'signin_ldap() - signin successful: {ldap_dn}')

    return util.handle_successful_login(
        request=request,
        udb=udb,
        login_type=login_type,
        target_url=str(util.url('/ui/profile')),
        full_name=username,
        idp_name='ldap',
        uid=ldap_dn,
        email=None,
        has_avatar=False,
        is_vetted=True,
    )


@router.get('/signout')
async def signout(request: starlette.requests.Request):
    response = util.redirect_internal('/ui/signin', **request.query_params)
    response.delete_cookie('pasta_token')
    response.delete_cookie('auth-token')
    return response
