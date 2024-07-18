import cryptography.hazmat.backends
import cryptography.x509
import daiquiri
import fastapi
import jwt
import requests
import starlette.requests
import starlette.responses

import pasta_token as pasta_token_
import user_db
import util
from config import Config

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

#
# Login
#


@router.get('/auth/login/microsoft')
async def login_microsoft(
    request: starlette.requests.Request,
):
    """Accept the initial login request from an EDI service and redirect to the
    Microsoft login endpoint.
    """
    target = request.query_params.get('target')
    log.debug(f'login_microsoft() target="{target}"')
    return util.redirect(
        Config.MICROSOFT_AUTH_ENDPOINT,
        client_id=Config.MICROSOFT_CLIENT_ID,
        response_type='code',
        redirect_uri=util.get_redirect_uri('microsoft', target),
        scope='openid profile email https://graph.microsoft.com/User.Read',
        response_mode='query',
        prompt='select_account',
    )


@router.get('/auth/login/microsoft/callback/{target:path}')
async def login_microsoft_callback(
    target,
    request: starlette.requests.Request,
    udb: user_db.UserDb = fastapi.Depends(user_db.udb),
):
    """On successful login, redeem a code for an access token. Otherwise, just redirect to the
    target URL.

    The access token is then used to get the user's information. The user's information is then used
    to create an authentication token for the user.

    The microsoft oauth service redirects to this endpoint with a code parameter after successful
    authentication.
    """
    code_str = request.query_params.get('code')
    if code_str is None:
        return util.redirect(target, error='Login cancelled')

    try:
        token_response = requests.post(
            Config.MICROSOFT_TOKEN_ENDPOINT,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            },
            data=util.build_query_string(
                client_id=Config.MICROSOFT_CLIENT_ID,
                code=code_str,
                redirect_uri=util.get_redirect_uri('microsoft', target),
                grant_type='authorization_code',
                client_secret=Config.MICROSOFT_CLIENT_SECRET,
            ),
        )
    except requests.RequestException:
        log.error('Login unsuccessful', exc_info=True)
        return util.redirect(target, error='Login unsuccessful')

    try:
        token_dict = token_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {token_response.text}', exc_info=True)
        return util.redirect(target, error='Login unsuccessful')

    if 'id_token' not in token_dict:
        util.log_dict(log.error, 'Login unsuccessful: token_dict', token_dict)
        return util.redirect(target, error='Login unsuccessful')

    jwt_unverified_header_dict = jwt.get_unverified_header(token_dict['id_token'])
    ms_pub_key = get_microsoft_public_key_by_kid(jwt_unverified_header_dict['kid'])
    user_dict = jwt.decode(
        token_dict['id_token'],
        ms_pub_key,
        algorithms=[jwt_unverified_header_dict['alg']],
        audience=Config.MICROSOFT_CLIENT_ID,
    )

    log.debug('-' * 80)
    log.debug('login_microsoft_callback() - login successful')
    util.log_dict(log.debug, 'jwt_unverified_header_dict', jwt_unverified_header_dict)
    util.log_dict(log.debug, 'token_dict', token_dict)
    util.log_dict(log.debug, 'user_dict', user_dict)
    log.debug('-' * 80)

    # 'sub' (subject) is the unique identifier for the user
    uid = user_dict['sub']
    # 'name' is the user's display name
    cname = user_dict['name']

    pasta_token = pasta_token_.make_pasta_token(uid=uid, groups=Config.AUTHENTICATED)

    given_name, family_name = cname.split(' ', 1) if ' ' in cname else (cname, '')

    # Update DB
    identity_row = udb.create_or_update_profile_and_identity(
        given_name=given_name,
        family_name=family_name,
        idp_name='microsoft',
        uid=uid,
        email=user_dict['email'],
        pasta_token=pasta_token,
    )

    # Redirect to privacy policy accept page if user hasn't accepted it yet
    if not identity_row.profile.privacy_policy_accepted:
        return util.redirect(
            '/auth/accept',
            target=target,
            pasta_token=identity_row.pasta_token,
            urid=identity_row.profile.urid,
            full_name=identity_row.profile.full_name,
            email=identity_row.profile.email,
            uid=identity_row.uid,
            idp_name=identity_row.idp_name,
            idp_token=token_dict['access_token'],
        )

    # Finally, redirect to the target URL with the authentication token
    return util.redirect_target(
        target=target,
        pasta_token=identity_row.pasta_token,
        urid=identity_row.profile.urid,
        full_name=identity_row.profile.full_name,
        email=identity_row.profile.email,
        uid=identity_row.uid,
        idp_name=identity_row.idp_name,
        idp_token=token_dict['access_token'],
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


@router.get('/auth/logout/microsoft')
async def logout_microsoft(
    request: starlette.requests.Request,
):
    """Receive the initial logout request from an EDI service and redirect to the
    Microsoft logout endpoint. The Microsoft logout endpoint will redirect back to the
    callback URL with a `post_logout_redirect_uri` parameter.
    """
    target = request.query_params.get('target')
    uid = request.query_params.get('uid')
    log.debug(f'logout_microsoft() target="{target}" uid="{uid}"')

    # request.base_url matches the route that points to this handler, except for
    # query parameters. We built onto the base_url to reach the next handler, which
    # is the callback handler.
    return util.redirect(
        Config.MICROSOFT_LOGOUT_ENDPOINT,
        client_id=Config.MICROSOFT_CLIENT_ID,
        post_logout_redirect_uri=util.get_redirect_uri('microsoft', target),
    )


@router.get('/auth/logout/microsoft/callback/{target:path}')
async def logout_microsoft_callback(target):
    """Receive the callback from the Microsoft logout endpoint and redirect to the
    target URL.

    Microsoft app registration must have the URL for this endpoint registered in the Web
    Redirect URIs section. The section includes both login and logout callbacks.

    The Microsoft logout endpoint calls the clear-session endpoint before redirecting to
    this callback URL.
    """
    log.debug(f'logout_microsoft_callback() target="{target}"')
    return util.redirect(target)


@router.get('/auth/logout/microsoft/clear-session')
async def logout_microsoft_clear_session(request: starlette.requests.Request):
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
