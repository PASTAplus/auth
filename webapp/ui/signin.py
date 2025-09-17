import daiquiri
import fastapi
import starlette.requests
import starlette.status

import db.models.profile
import util.avatar
import util.dependency
import util.login
import util.edi_token
import util.pasta_ldap
import util.redirect
import util.template
import util.url
from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


#
# UI routes
#


@router.get('/ui/signin')
async def get_ui_signin(
    request: starlette.requests.Request,
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    if token_profile_row:
        return util.redirect.internal('/ui/profile')
    return util.template.templates.TemplateResponse(
        'signin.html',
        {
            # Base
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




@router.get('/ui/signin/merge')
async def get_ui_signin(
    request: starlette.requests.Request,
):
    # if token:
    #     return util.redirect.internal('/ui/profile')
    return util.template.templates.TemplateResponse(
        'signin-merge.html',
        {
            # Base
            'profile': None,
            #
            'request': request,
            # 'login_type': 'client',
            # 'target_url': Config.SERVICE_BASE_URL + '/ui/identity',
            'error': request.query_params.get('error'),
            'skeleton_profile': True,
        },
    )





@router.get('/ui/signin/link')
async def get_ui_signin_link(
    request: starlette.requests.Request,
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    return util.template.templates.TemplateResponse(
        'signin.html',
        {
            # Base
            'profile': token_profile_row,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            # Page
            'request': request,
            'login_type': 'link',
            'target_url': Config.SERVICE_BASE_URL + '/ui/identity',
            'title': 'Link Account',
            'text':
            # language=html
            f"""
            <p>
            Sign in to the account you wish to link to this profile.
            </p>
            <p>
            Linking accounts allows you to sign in with multiple identity providers.
            </p>
            <p>
                <a href='{util.url.url('/ui/identity')}' class='icon-text-button'>
                    <span><img src='{util.url.url('/static/svg/back.svg')}' alt='Back to Accounts'></span>
                    <span>Back to Accounts</span>
                </a>
            </p>
            """,
        },
    )


@router.get('/ui/signin/reset')
async def get_ui_signin_reset(
    request: starlette.requests.Request,
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    return util.template.templates.TemplateResponse(
        'signin-reset-pw.html',
        {
            # Base
            'profile': token_profile_row,
            'request': request,
        },
    )


#
# Internal routes
#


@router.post('/ui/api/signin/ldap')
async def post_signin_ldap(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Handle LDAP sign in from the Auth sign in page. This duplicates some of the logic in
    idp/ldap.py, but interacts with the browser instead of a server side client.
    """
    form_data = await request.form()
    login_type = form_data.get('login_type')
    username = form_data.get('username')
    password = form_data.get('password')
    ldap_dn = get_ldap_dn(username)

    if not util.pasta_ldap.bind(ldap_dn, password):
        return util.redirect.internal('/ui/signin', error='Sign in failed. Please try again.')

    log.debug(f'signin_ldap() - signin successful: {ldap_dn}')

    return await util.login.handle_successful_login(
        request=request,
        dbi=dbi,
        token_profile_row=token_profile_row,
        login_type=login_type,
        target_url=str(util.url.url('/ui/profile')),
        idp_name=db.models.profile.IdpName.LDAP,
        idp_uid=ldap_dn,
        common_name=username,
        email=None,
        has_avatar=False,
    )


def get_ldap_dn(idp_uid: str) -> str:
    return f'uid={idp_uid},o=EDI,dc=edirepository,dc=org'


@router.get('/signout')
async def signout(request: starlette.requests.Request):
    response = util.redirect.internal('/ui/signin', **request.query_params)
    response.delete_cookie('edi-token')
    response.delete_cookie('auth-token')
    return response
