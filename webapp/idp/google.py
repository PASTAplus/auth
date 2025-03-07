import re

import daiquiri
import fastapi
import requests
import starlette.requests
import starlette.status

import db.iface
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
    login_type = request.query_params.get('login_type', 'client')
    target_url = request.query_params.get('target')
    log.debug(f'login_google() login_type="{login_type}" target_url="{target_url}"')

    google_provider_cfg = get_google_provider_cfg()

    if google_provider_cfg is None:
        log.error(
            'Login unsuccessful: Cannot download Google provider configuration',
            exc_info=True,
        )
        return util.redirect_to_client_error(target_url, 'Login unsuccessful')

    util.log_dict(log.debug, 'google_provider_cfg', google_provider_cfg)

    return util.redirect_to_idp(
        google_provider_cfg['authorization_endpoint'],
        'google',
        login_type,
        target_url,
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
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
):
    login_type, target_url = util.unpack_state(request.query_params.get('state'))
    log.debug(f'callback_google() login_type="{login_type}" target_url="{target_url}"')

    code_str = request.query_params.get('code')
    if code_str is None:
        return util.redirect_to_client_error(target_url, 'Login cancelled')

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
                    util.get_redirect_uri('google').replace_query_params(code=code_str)
                ),
                redirect_uri=util.get_redirect_uri('google'),
                grant_type='authorization_code',
            ),
        )
    except requests.RequestException:
        log.error('Login unsuccessful', exc_info=True)
        return util.redirect_to_client_error(target_url, 'Login unsuccessful')

    try:
        token_dict = token_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {token_response.text}', exc_info=True)
        return util.redirect_to_client_error(target_url, 'Login unsuccessful')

    if 'error' in token_dict:
        log.error(f'Login unsuccessful: {token_dict["error"]}', exc_info=True)
        return util.redirect_to_client_error(target_url, 'Login unsuccessful')

    try:
        userinfo_response = requests.get(
            google_provider_cfg['userinfo_endpoint'],
            headers={
                'Authorization': f'Bearer {token_dict["access_token"]}',
            },
        )
    except requests.RequestException:
        log.error('Login unsuccessful', exc_info=True)
        return util.redirect_to_client_error(target_url, 'Login unsuccessful')

    try:
        user_dict = userinfo_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {userinfo_response.text}', exc_info=True)
        return util.redirect_to_client_error(target_url, 'Login unsuccessful')

    if not user_dict.get('email_verified'):
        return util.redirect_to_client_error(
            target_url, 'Login unsuccessful: Email not verified'
        )

    # Fetch the avatar
    has_avatar = False
    try:
        avatar = get_user_avatar(token_dict['access_token'])
    except fastapi.HTTPException as e:
        log.error(f'Failed to fetch user avatar: {e.detail}')
    else:
        util.save_avatar(avatar, 'google', user_dict['sub'])
        has_avatar = True

    log.debug('-' * 80)
    log.debug('login_google_callback() - login successful')
    util.log_dict(log.debug, 'token_dict', token_dict)
    util.log_dict(log.debug, 'user_dict', user_dict)
    log.debug('-' * 80)

    return util.handle_successful_login(
        request=request,
        udb=udb,
        login_type=login_type,
        target_url=target_url,
        full_name=user_dict["name"],
        idp_name='google',
        uid=user_dict['sub'],
        email=user_dict['email'],
        has_avatar=has_avatar,
        is_vetted=False,
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
    target_url = request.query_params.get('target')
    uid = request.query_params.get('uid')
    idp_token = request.query_params.get('idp_token')

    log.debug(
        f'revoke_google() target_url="{target_url}" uid="{uid}" idp_token="{idp_token}"'
    )

    try:
        response = requests.post(
            get_google_provider_cfg()['revocation_endpoint'],
            params={'token': idp_token},
        )
    except requests.RequestException:
        log.error('Revoke unsuccessful', exc_info=True)
        return util.redirect_to_client_error(target_url, 'Revoke unsuccessful')
    else:
        if response.status_code != starlette.status.HTTP_200_OK:
            log.error(f'Revoke unsuccessful: {response.text}', exc_info=True)
            return util.redirect_to_client_error(target_url, 'Revoke unsuccessful')

    return util.redirect(target_url)


#
# Util
#


def get_user_avatar(access_token):
    response_url = requests.get(
        'https://people.googleapis.com/v1/people/me?personFields=photos',
        headers={'Authorization': f'Bearer {access_token}'},
    )

    try:
        response_dict = response_url.json()
    except requests.JSONDecodeError:
        raise fastapi.HTTPException(
            status_code=starlette.status.HTTP_404_NOT_FOUND,
            detail=response_url.text,
        )

    util.log_dict(log.debug, 'google: get_user_avatar()', response_dict)

    photos = response_dict.get('photos')
    if not photos:
        raise fastapi.HTTPException(
            status_code=starlette.status.HTTP_404_NOT_FOUND,
            detail='No photos found',
        )

    # Assuming the first photo is the highest resolution available
    avatar_url = photos[0].get('url')
    if avatar_url is None:
        raise fastapi.HTTPException(
            status_code=starlette.status.HTTP_404_NOT_FOUND,
            detail='No avatar URL found',
        )

    # Fetch higher resolution avatar
    hirez_avatar_url = re.sub(r'=s\d+$', '=s500', avatar_url)
    response_img = requests.get(hirez_avatar_url)
    if not response_img.ok:
        raise fastapi.HTTPException(
            status_code=starlette.status.HTTP_404_NOT_FOUND,
            detail=response_img.text,
        )
    return response_img.content
