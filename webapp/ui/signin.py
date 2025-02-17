import daiquiri
import fastapi
import starlette.requests
import starlette.status

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


# UI routes

@router.get('/ui/signin')
async def get_ui_signin(
    request: starlette.requests.Request,
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    if token:
        return util.utils.redirect_internal('/ui/profile')
    return util.template.templates.TemplateResponse(
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
async def get_ui_signin_link(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    profile_row = udb.get_profile(token.pasta_id)
    return util.template.templates.TemplateResponse(
        'signin.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(profile_row),
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
async def get_ui_signin_reset(
    request: starlette.requests.Request,
    # udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    return util.template.templates.TemplateResponse(
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
async def post_signin_ldap(
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
    ldap_dn = util.utils.get_ldap_dn(username)

    if not util.pasta_ldap.bind(ldap_dn, password):
        return util.utils.redirect_internal(
            '/ui/signin', error='Sign in failed. Please try again.'
        )

    log.debug(f'signin_ldap() - signin successful: {ldap_dn}')

    return util.utils.handle_successful_login(
        request=request,
        udb=udb,
        login_type=login_type,
        target_url=str(util.utils.url('/ui/profile')),
        full_name=username,
        idp_name='ldap',
        idp_uid=ldap_dn,
        email=None,
        has_avatar=False,
        is_vetted=True,
    )


@router.get('/signout')
async def signout(request: starlette.requests.Request):
    response = util.utils.redirect_internal('/ui/signin', **request.query_params)
    response.delete_cookie('pasta_token')
    response.delete_cookie('auth-token')
    return response
