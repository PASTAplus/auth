import cryptography.hazmat.backends
import cryptography.x509
import daiquiri
import fastapi
import jwt
import requests
import sqlalchemy.exc
import starlette.requests
import starlette.responses

import db.models.profile
import util.avatar
import util.dependency
import util.login
import util.pretty
import util.redirect
import util.url
from config import Config

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

#
# Login
#


@router.get('/login/microsoft')
async def get_login_microsoft(
    request: starlette.requests.Request,
):
    """Accept the initial login request from an EDI service and redirect to the
    Microsoft login endpoint.
    """
    login_type = request.query_params.get('login_type', 'client')
    target_url = request.query_params.get('target')
    log.debug(f'login_microsoft() login_type="{login_type}" target_url="{target_url}"')

    return util.redirect.idp(
        Config.MICROSOFT_AUTH_ENDPOINT,
        db.models.profile.IdpName.MICROSOFT,
        login_type,
        target_url,
        client_id=Config.MICROSOFT_CLIENT_ID,
        scope='openid profile email https://graph.microsoft.com/User.Read https://graph.microsoft.com/User.ReadBasic.All',
        # scope='read:user',
        # prompt='consent',
        # prompt='login',
        prompt='select_account',
        response_type='code',
        response_mode='query',
    )


@router.get('/callback/microsoft')
async def get_callback_microsoft(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """On successful login, redeem a code for an access token. Otherwise, just redirect to the
    target URL.

    The access token is then used to get the user's information. The user's information is then used
    to create an authentication token for the user.

    The microsoft oauth service redirects to this endpoint with a code parameter after successful
    authentication.
    """
    login_type, target_url = util.login.unpack_state(request.query_params.get('state'))
    log.debug(f'callback_microsoft() login_type="{login_type}" target_url="{target_url}"')

    code_str = request.query_params.get('code')
    if code_str is None:
        return util.redirect.client_error(target_url, 'Login cancelled')

    try:
        token_response = requests.post(
            Config.MICROSOFT_TOKEN_ENDPOINT,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            },
            data=util.url.build_query_string(
                client_id=Config.MICROSOFT_CLIENT_ID,
                client_secret=Config.MICROSOFT_CLIENT_SECRET,
                code=code_str,
                redirect_uri=util.login.get_redirect_uri('microsoft'),
                grant_type='authorization_code',
            ),
        )
    except requests.RequestException:
        log.error('Login unsuccessful', exc_info=True)
        return util.redirect.client_error(target_url, 'Login unsuccessful')

    try:
        token_dict = token_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {token_response.text}', exc_info=True)
        return util.redirect.client_error(target_url, 'Login unsuccessful')

    if 'id_token' not in token_dict:
        util.pretty.log_dict(log.error, 'Login unsuccessful: token_dict', token_dict)
        return util.redirect.client_error(target_url, 'Login unsuccessful')

    jwt_unverified_header_dict = jwt.get_unverified_header(token_dict['id_token'])
    ms_pub_key = get_microsoft_public_key_by_kid(jwt_unverified_header_dict['kid'])
    user_dict = jwt.decode(
        token_dict['id_token'],
        ms_pub_key,
        algorithms=[jwt_unverified_header_dict['alg']],
        audience=Config.MICROSOFT_CLIENT_ID,
    )

    idp_uid = user_dict['sub']

    avatar_img = None
    avatar_ver = None
    try:
        profile_row = await dbi.get_profile_by_idp(
            idp_name=db.models.profile.IdpName.MICROSOFT,
            idp_uid=idp_uid,
        )
        avatar_ver = 'TEST'
        if profile_row.avatar_ver != avatar_ver:
            try:
                avatar_img = get_user_avatar(user_dict['avatar_url'])
            except fastapi.HTTPException as e:
                log.error(f'Failed to fetch user avatar: {e.detail}')
    except sqlalchemy.exc.NoResultFound:
        pass

    log.debug('-' * 80)
    log.debug('login_microsoft_callback() - login successful')
    util.pretty.log_dict(log.debug, 'jwt_unverified_header_dict', jwt_unverified_header_dict)
    util.pretty.log_dict(log.debug, 'token_dict', token_dict)
    util.pretty.log_dict(log.debug, 'user_dict', user_dict)
    log.debug('-' * 80)

    return await util.login.handle_successful_login(
        request=request,
        dbi=dbi,
        token_profile_row=token_profile_row,
        login_type=login_type,
        target_url=target_url,
        idp_name=db.models.profile.IdpName.MICROSOFT,
        idp_uid=idp_uid,
        common_name=user_dict['name'],
        email=user_dict['email'],
        avatar_img=avatar_img,
        avatar_ver=avatar_ver,
    )


def get_microsoft_public_key_by_kid(kid):
    """Return the public key for the given kid (key ID)"""
    MICROSOFT_KEYS_URL = f'https://login.microsoftonline.com/common/discovery/v2.0/keys'
    response = requests.get(MICROSOFT_KEYS_URL)
    response_dict = response.json()

    x5c_str = None

    for key_dict in response_dict['keys']:
        if key_dict['kid'] == kid:
            x5c_str = key_dict['x5c'][0]

    if x5c_str is None:
        raise ValueError(f'No key found for kid "{kid}"')

    cert_pem = f'-----BEGIN CERTIFICATE-----\n{x5c_str}\n-----END CERTIFICATE-----'

    cert_obj = cryptography.x509.load_pem_x509_certificate(
        cert_pem.encode('utf-8'), cryptography.hazmat.backends.default_backend()
    )

    return cert_obj.public_key()


#
# Logout
#


@router.get('/logout/microsoft')
async def get_logout_microsoft(
    request: starlette.requests.Request,
):
    """Receive the initial logout request from an EDI service and redirect to the
    Microsoft logout endpoint. The Microsoft logout endpoint will redirect back to the
    callback URL with a `post_logout_redirect_uri` parameter.
    """
    target_url = request.query_params.get('target')
    idp_uid = request.query_params.get('idp_uid')
    log.debug(f'logout_microsoft() target_url="{target_url}" idp_uid="{idp_uid}"')

    # request.base_url matches the route that points to this handler, except for
    # query parameters. We built onto the base_url to reach the next handler, which
    # is the callback handler.
    return util.redirect.redirect(
        Config.MICROSOFT_LOGOUT_ENDPOINT,
        client_id=Config.MICROSOFT_CLIENT_ID,
        post_logout_redirect_uri=util.login.get_redirect_uri('microsoft'),
    )


@router.get('/logout/microsoft/callback/{target_url}')
async def get_logout_microsoft_callback(target_url):
    """Receive the callback from the Microsoft logout endpoint and redirect to the
    target URL.

    Microsoft app registration must have the URL for this endpoint registered in the Web
    Redirect URIs section. The section includes both login and logout callbacks.

    The Microsoft logout endpoint calls the clear-session endpoint before redirecting to
    this callback URL.
    """
    log.debug(f'logout_microsoft_callback() target_url="{target_url}"')
    return util.redirect.redirect(target_url)


@router.get('/logout/microsoft/clear-session')
async def get_logout_microsoft_clear_session(request: starlette.requests.Request):
    """Receive the redirect from the Microsoft logout endpoint and redirect to the
    target URL.

    This endpoint is called by the browser before the browser is redirected to the
    callback in auth, which then redirects back to the target.

    This URL is configured as the 'Front-channel logout URL' in the Microsoft app
    registration.

    The Microsoft logout endpoint then redirects to the 'post_logout_redirect_uri' URL,
    which is the URL that initiated the logout request.

    Example redirect URL:
    /auth/logout/microsoft/clear-session
    ?sid=M.417303542816503182
    &iss=https://login.microsoftonline.com/9188040d-6c67-4c5b-b112-36a304b66dad/v2.0

    sid = session ID
    iss = issuer (entity that created and signed the token)
    """
    log.debug(f'logout_microsoft_clear_session() args={request.query_params}')
    return starlette.responses.Response(content='OK')


#
# Util
#


def get_user_avatar(access_token):
    """Fetch the user's avatar from Microsoft Graph API."""
    try:
        response = requests.get(
            'https://graph.microsoft.com/v1.0/me/photo/$value',
            headers={'Authorization': f'Bearer {access_token}', 'Accept': 'image/*'},
        )
        if response.ok:
            return response.content
    except requests.RequestException as e:
        log.error(f'Error fetching user avatar: {e}')
    return None
