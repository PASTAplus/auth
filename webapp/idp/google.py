import daiquiri
import fastapi
import requests
import starlette.requests
import starlette.status

import pasta_token as pasta_token_
import user_db
import util
from config import Config

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

# https://developers.google.com/identity/protocols/oauth2

#
# Login
#


@router.get('/login/google')
async def login_google(
    request: starlette.requests.Request,
):
    """Accept the initial login request from an EDI service and redirect to the
    Google login endpoint.
    """
    target = request.query_params.get('target')
    log.debug(f'login_google() target="{target}"')

    google_provider_cfg = get_google_provider_cfg()

    if google_provider_cfg is None:
        log.error(
            'Login unsuccessful: Cannot download Google provider configuration',
            exc_info=True,
        )
        return util.redirect(target, error='Login unsuccessful')

    util.log_dict(log.debug, 'google_provider_cfg', google_provider_cfg)

    authorization_endpoint = google_provider_cfg['authorization_endpoint']

    return util.redirect_to_idp(
        authorization_endpoint,
        'google',
        target,
        client_id=Config.GOOGLE_CLIENT_ID,
        scope='openid email profile',
        # scope='read:user',
        # prompt='consent',
        prompt='login',
        response_type='code',
    )


@router.get('/callback/google')
async def callback_google(
    request: starlette.requests.Request,
    udb: user_db.UserDb = fastapi.Depends(user_db.udb),
):
    target = request.cookies.get('target')
    log.debug(f'callback_google() target="{target}"')

    code_str = request.query_params.get('code')
    if code_str is None:
        return util.redirect(target, error='Login cancelled')

    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg['token_endpoint']

    try:
        token_response = requests.post(
            token_endpoint,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            },
            data=util.build_query_string(
                client_id=Config.GOOGLE_CLIENT_ID,
                client_secret=Config.GOOGLE_CLIENT_SECRET,
                code=code_str,
                authorization_response=str(
                    util.get_redirect_uri("google").replace_query_params(code=code_str)
                ),
                redirect_uri=util.get_redirect_uri('google'),
                grant_type='authorization_code',
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

    if 'error' in token_dict:
        log.error(f'Login unsuccessful: {token_dict["error"]}', exc_info=True)
        return util.redirect(target, error='Login unsuccessful')

    try:
        userinfo_response = requests.get(
            google_provider_cfg['userinfo_endpoint'],
            headers={
                'Authorization': f'Bearer {token_dict["access_token"]}',
            },
        )
    except requests.RequestException:
        log.error('Login unsuccessful', exc_info=True)
        return util.redirect(target, error='Login unsuccessful')

    try:
        user_dict = userinfo_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {userinfo_response.text}', exc_info=True)
        return util.redirect(target, error='Login unsuccessful')

    if not user_dict.get('email_verified'):
        return util.redirect(target, error='Login unsuccessful: Email not verified')

    log.debug('-' * 80)
    log.debug('login_google_callback() - login successful')
    util.log_dict(log.debug, 'token_dict', token_dict)
    util.log_dict(log.debug, 'user_dict', user_dict)
    log.debug('-' * 80)

    # TODO: Move from email to sub when clients are ready.
    uid = user_dict['email']
    groups = Config.AUTHENTICATED

    pasta_token = pasta_token_.make_pasta_token(uid=uid, groups=groups)

    # Update DB
    identity_row = udb.create_or_update_profile_and_identity(
        given_name=user_dict['given_name'],
        family_name=user_dict['family_name'],
        idp_name='google',
        uid=user_dict['sub'],
        email=user_dict['email'],
        pasta_token=pasta_token,
    )

    # Redirect to privacy policy accept page if user hasn't accepted it yet
    if not identity_row.profile.privacy_policy_accepted:
        return util.redirect(
            '/login/accept',
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


@router.get('/revoke/google')
async def revoke_google(
    request: starlette.requests.Request,
):
    target = request.query_params.get('target')
    uid = request.query_params.get('uid')
    idp_token = request.query_params.get('idp_token')

    log.debug(f'revoke_google() target="{target}" uid="{uid}" idp_token="{idp_token}"')

    try:
        response = requests.post(
            get_google_provider_cfg()['revocation_endpoint'],
            params={'token': idp_token},
        )
    except requests.RequestException:
        log.error('Revoke unsuccessful', exc_info=True)
        return util.redirect(target, error='Revoke unsuccessful')
    else:
        if response.status_code != 200:
            log.error(f'Revoke unsuccessful: {response.text}', exc_info=True)
            return util.redirect(target, error='Revoke unsuccessful')

    return util.redirect(target)
