import daiquiri
import fastapi
import oauthlib.oauth2
import requests

import pasta_token as pasta_token_
import user_db
import util
from config import Config
import starlette.responses
import starlette.requests
import starlette.status


log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

# https://developers.google.com/identity/protocols/oauth2

#
# Login
#


@router.get('/auth/login/google')
async def login_google(
    request: starlette.requests.Request,
):
    """Accept the initial login request from an EDI service and redirect to the
    Google login endpoint.
    """
    target = request.query_params.get('target')
    log.debug(f'login_google() target="{target}"')

    client = oauthlib.oauth2.WebApplicationClient(Config.GOOGLE_CLIENT_ID)
    google_provider_cfg = get_google_provider_cfg()

    if google_provider_cfg is None:
        log.error(
            'Login unsuccessful: Cannot download Google provider configuration',
            exc_info=True,
        )
        return util.redirect(target, error='Login unsuccessful')

    util.log_dict(log.debug, 'google_provider_cfg', google_provider_cfg)

    authorization_endpoint = google_provider_cfg['authorization_endpoint']

    # noinspection PyNoneFunctionAssignment
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=get_redirect_uri(target),
        scope=['openid', 'email', 'profile'],
        prompt='login',
    )

    log.debug(f'login_google() request_uri="{request_uri}"')

    # noinspection PyTypeChecker
    return starlette.responses.RedirectResponse(
        request_uri,
        # RedirectResponse returns 307 temporary redirect by default
        status_code=starlette.status.HTTP_302_FOUND,
    )


@router.get('/auth/login/google/callback/{target:path}')
async def login_google_callback(
    target,
    request: starlette.requests.Request,
    udb: user_db.UserDb = fastapi.Depends(user_db.udb),
):
    log.debug(f'login_google_callback() target="{target}"')

    code_str = request.query_params.get('code')
    if code_str is None:
        return util.redirect(target, error='Login cancelled')

    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg['token_endpoint']

    client = oauthlib.oauth2.WebApplicationClient(Config.GOOGLE_CLIENT_ID)
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=f'{get_redirect_uri(target)}?code={code_str}',
        redirect_url=get_redirect_uri(target),
        code=code_str,
    )
    try:
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(Config.GOOGLE_CLIENT_ID, Config.GOOGLE_CLIENT_SECRET),
        )
    except requests.RequestException as e:
        log.error('Login unsuccessful', exc_info=True)
        return util.redirect(target, error='Login unsuccessful')

    try:
        token_dict = token_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {token_response.text}', exc_info=True)
        return util.redirect(target, error='Login unsuccessful')

    try:
        client.parse_request_body_response(token_response.text)
    except Exception:
        log.error(f'Login unsuccessful: {token_response.text}', exc_info=True)
        return util.redirect(target, error=f'Login unsuccessful')

    userinfo_endpoint = google_provider_cfg['userinfo_endpoint']
    uri, headers, body = client.add_token(userinfo_endpoint)

    try:
        userinfo_response = requests.get(uri, headers=headers, data=body)
    except requests.RequestException:
        log.error('Login unsuccessful', exc_info=True)
        return util.redirect(target, error='Login unsuccessful')

    try:
        user_dict = userinfo_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {userinfo_response.text}', exc_info=True)
        return util.redirect(target, error=f'Login unsuccessful')

    if not user_dict.get('email_verified'):
        return util.redirect(target, error='Login unsuccessful: Email not verified')

    log.debug('-' * 80)
    log.debug('login_google_callback() - login successful')
    util.log_dict(log.debug, 'token_dict', token_dict)
    util.log_dict(log.debug, 'user_dict', user_dict)
    log.debug('-' * 80)

    # TODO: Move from email to sub when clients are ready.
    uid = user_dict['email']
    cname = f'{user_dict["given_name"]} {user_dict["family_name"]}'
    groups = Config.AUTHENTICATED

    pasta_token = pasta_token_.make_pasta_token(uid=uid, groups=groups)

    # Update DB

    identity = udb.get_identity(idp='google', uid=uid)
    if identity is None:
        urid = udb.get_new_urid()
        udb.create_profile(
            urid=urid,
            given_name=user_dict['given_name'],
            family_name=user_dict['family_name'],
        )
        udb.create_identity(
            urid=urid,
            idp='google',
            uid=uid,
            email=uid,
        )
    else:
        urid = identity.urid

    udb.set_token(urid=urid, token=pasta_token)

    # Redirect to privacy policy accept page if user hasn't accepted it yet
    if not udb.is_privacy_policy_accepted(urid=urid):
        return util.redirect(
            '/auth/accept',
            uid=uid,
            target=target,
            idp='google',
            idp_token=token_dict['access_token'],
        )

    # Finally, redirect to the target URL with the authentication token
    return util.redirect(
        target,
        token=pasta_token,
        cname=cname,
        idp='google',
        idp_token=token_dict['access_token'],
    )


def get_redirect_uri(target):
    return f'{Config.CALLBACK_BASE_URL}/google/callback/{target}'


def get_google_provider_cfg():
    try:
        discovery_response = requests.get(Config.GOOGLE_DISCOVERY_URL)
    except requests.RequestException as e:
        log.error(f'Error downloading Google discovery: {e}')
        return None
    try:
        return discovery_response.json()
    except requests.JSONDecodeError as e:
        log.error(f'Error decoding Google discovery response: {e}')


#
# Revoke application authorization
#


@router.get('/auth/revoke/google')
async def revoke_google():
    target = request.query_params.get('target')
    uid = request.query_params.get('uid')
    idp_token = request.query_params.get('idp_token')

    log.debug(f'revoke_google() target="{target}" uid="{uid}" idp_token="{idp_token}"')

    try:
        response = requests.post(
            get_google_provider_cfg()['revocation_endpoint'],
            params={'token': idp_token},
        )
    except requests.RequestException as e:
        log.error('Revoke unsuccessful', exc_info=True)
        return util.redirect(target, error='Revoke unsuccessful')
    else:
        if response.status_code != 200:
            log.error(f'Revoke unsuccessful: {response.text}', exc_info=True)
            return util.redirect(target, error='Revoke unsuccessful')

    return util.redirect(target)
