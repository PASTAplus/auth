import cryptography.hazmat.backends
import cryptography.x509
import daiquiri
import flask
import flask.blueprints
import jwt
import requests

from webapp import pasta_token as pasta_token_
from webapp import user_db
from webapp import util
from webapp.config import Config

log = daiquiri.getLogger(__name__)
blueprint = flask.blueprints.Blueprint('microsoft', __name__)

#
# Login
#


@blueprint.route('/auth/login/microsoft', methods=['GET'])
def login_microsoft():
    """Accept the initial login request from an EDI service and redirect to the
    Microsoft login endpoint.
    """
    target = flask.request.args.get("target")
    log.debug(f'login_microsoft() target="{target}"')
    return util.redirect(
        Config.MICROSOFT_AUTH_ENDPOINT,
        client_id=Config.MICROSOFT_CLIENT_ID,
        response_type='code',
        redirect_uri=f'{Config.CALLBACK_BASE_URL}/microsoft/callback/{target}',
        scope='openid profile email https://graph.microsoft.com/User.Read',
        response_mode='query',
        prompt='select_account',
    )


@blueprint.route('/auth/login/microsoft/callback/<path:target>', methods=['GET'])
def login_microsoft_callback(target):
    """On successful login, redeem a code for an access token. Otherwise, just redirect to the
    target URL.

    The access token is then used to get the user's information. The user's information is then used
    to create an authentication token for the user.

    The microsoft oauth service redirects to this endpoint with a code parameter after successful
    authentication.
    """
    code_str = flask.request.args.get('code')
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
                redirect_uri=flask.request.base_url,
                grant_type='authorization_code',
                client_secret=Config.MICROSOFT_CLIENT_SECRET,
            ),
        )
    except requests.RequestException as e:
        log.error('Login unsuccessful', exc_info=True)
        return util.redirect(target, error='Login unsuccessful')

    try:
        token_dict = token_response.json()
    except requests.JSONDecodeError as e:
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

    # Update DB
    udb = user_db.UserDb()
    udb.set_user(uid=uid, token=pasta_token, cname=cname)

    # Redirect to privacy policy accept page if user hasn't accepted it yet
    if not udb.is_privacy_policy_accepted(uid=uid):
        return util.redirect(
            '/auth/accept',
            uid=uid,
            target=target,
            idp='microsoft',
            idp_token=token_dict['access_token'],
        )

    # Finally, redirect to the target URL with the authentication token
    return util.redirect(
        target,
        token=pasta_token,
        cname=cname,
        idp='microsoft',
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


@blueprint.route('/auth/logout/microsoft', methods=['GET'])
def logout_microsoft():
    """Receive the initial logout request from an EDI service and redirect to the
    Microsoft logout endpoint. The Microsoft logout endpoint will redirect back to the
    callback URL with a `post_logout_redirect_uri` parameter.
    """
    target = flask.request.args.get("target")
    uid = flask.request.args.get('uid')
    log.debug(f'logout_microsoft() target="{target}" uid="{uid}"')

    # flask.request.base_url matches the route that points to this handler, except for
    # query parameters. We built onto the base_url to reach the next handler, which
    # is the callback handler.
    return util.redirect(
        Config.MICROSOFT_LOGOUT_ENDPOINT,
        client_id=Config.MICROSOFT_CLIENT_ID,
        post_logout_redirect_uri=f'{Config.CALLBACK_BASE_URL}/microsoft/callback/{target}',
        # post_logout_redirect_uri=f'{flask.request.base_url}/callback/{target}',
    )


@blueprint.route('/auth/logout/microsoft/callback/<path:target>', methods=['GET'])
def logout_microsoft_callback(target):
    """Receive the callback from the Microsoft logout endpoint and redirect to the
    target URL.

    Microsoft app registration must have the URL for this endpoint registered in the Web
    Redirect URIs section. The section includes both login and logout callbacks.

    The Microsoft logout endpoint calls the clear-session endpoint before redirecting to
    this callback URL.
    """
    log.debug(f'logout_microsoft_callback() target="{target}"')
    return util.redirect(target)


@blueprint.route('/auth/logout/microsoft/clear-session', methods=['GET'])
def logout_microsoft_clear_session():
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
    log.debug(f'logout_microsoft_clear_session() args={flask.request.args}')
    return 'OK', 200
