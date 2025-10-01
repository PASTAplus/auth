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
            'request': request,
            'profile': None,
            'avatar_url': None,
            'error_msg': request.query_params.get('error'),
            'info_msg': request.query_params.get('info'),
            # Page
            'login_type': 'client',
            'target_url': Config.SERVICE_BASE_URL + '/ui/profile',
            'title': 'Sign in',
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
            'request': request,
            'profile': None,
            'avatar_url': None,
            'error_msg': request.query_params.get('error'),
            'info_msg': request.query_params.get('info'),
            # Page
            # 'login_type': 'client',
            # 'target_url': Config.SERVICE_BASE_URL + '/ui/identity',
            'skeleton_profile': True,
        },
    )


@router.get('/ui/signin/link')
async def get_ui_signin_link(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    return util.template.templates.TemplateResponse(
        'signin.html',
        {
            # Base
            'request': request,
            'profile': token_profile_row,
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row),
            'error_msg': request.query_params.get('error'),
            'info_msg': request.query_params.get('info'),
            # Page
            'login_type': 'link',
            'target_url': Config.SERVICE_BASE_URL + '/ui/identity',
            'title': 'Link Profile',
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
        fetch_avatar_func=None,
        avatar_ver=None,
    )


def get_ldap_dn(idp_uid: str) -> str:
    return f'uid={idp_uid},o=EDI,dc=edirepository,dc=org'


@router.get('/signout')
async def signout(request: starlette.requests.Request):
    response = util.redirect.internal('/ui/signin', **request.query_params)
    response.delete_cookie('edi-token')
    response.delete_cookie('auth-token')
    return response
