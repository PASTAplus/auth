import functools
import json

import daiquiri
import fastapi
import requests
import sqlalchemy.exc
import starlette.requests
import starlette.status

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


@router.get('/login/github')
async def get_login_github(
    request: starlette.requests.Request,
):
    """Accept the initial login request from an EDI service and redirect to the
    GitHub login endpoint.
    """
    login_type = request.query_params.get('login_type', 'client')
    target_url = request.query_params.get('target')
    log.debug(f'login_github() login_type="{login_type}" target_url="{target_url}"')

    return util.redirect.idp(
        Config.GITHUB_AUTH_ENDPOINT,
        db.models.profile.IdpName.GITHUB,
        login_type,
        target_url,
        client_id=Config.GITHUB_CLIENT_ID,
        scope='read:user',
        prompt='consent',
        # prompt='login',
    )


@router.get('/callback/github')
async def get_callback_github(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    # token_profile_row is None if the user is logging in
    # token_profile_row is set if the user is linking a profile
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    login_type, target_url = util.login.unpack_state(request.query_params.get('state'))
    log.debug(f'callback_github() login_type="{login_type}" target_url="{target_url}"')

    if is_error(request):
        log.error(get_error_message(request))
        return util.redirect.client_error(target_url, 'Login failed')

    code_str = request.query_params.get('code')
    if code_str is None:
        return util.redirect.client_error(target_url, 'Login cancelled')

    try:
        token_response = requests.post(
            Config.GITHUB_TOKEN_ENDPOINT,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            },
            data=util.url.build_query_string(
                client_id=Config.GITHUB_CLIENT_ID,
                client_secret=Config.GITHUB_CLIENT_SECRET,
                code=code_str,
                authorization_response=str(
                    util.login.get_redirect_uri('github').replace_query_params(code=code_str)
                ),
                redirect_uri=util.login.get_redirect_uri('github'),
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

    if 'error' in token_dict:
        log.error(f'Login unsuccessful: {token_dict["error"]}', exc_info=True)
        return util.redirect.client_error(target_url, 'Login unsuccessful')

    try:
        userinfo_response = requests.get(
            Config.GITHUB_USER_ENDPOINT,
            headers={
                'Authorization': f'Bearer {token_dict["access_token"]}',
            },
        )
    except requests.RequestException:
        log.error('Login unsuccessful', exc_info=True)
        return util.redirect.client_error(target_url, 'Login unsuccessful')

    try:
        user_dict = userinfo_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {userinfo_response.text}', exc_info=True)
        return util.redirect.client_error(target_url, 'Login unsuccessful')

    idp_uid = user_dict['html_url']
    log.debug('-' * 80)
    log.debug('github_callback() - login successful')
    util.pretty.log_dict(log.debug, 'token_dict', token_dict)
    util.pretty.log_dict(log.debug, 'user_dict', user_dict)
    log.debug('-' * 80)

    return await util.login.handle_successful_login(
        request=request,
        dbi=dbi,
        token_profile_row=token_profile_row,
        login_type=login_type,
        target_url=target_url,
        idp_name=db.models.profile.IdpName.GITHUB,
        idp_uid=idp_uid,
        common_name=user_dict.get('name') or user_dict.get('login') or idp_uid,
        email=user_dict.get('email'),
        fetch_avatar_func=functools.partial(fetch_user_avatar, user_dict['avatar_url']),
        avatar_ver=util.url.get_query_param(user_dict['avatar_url'], 'v'),
    )


#
# Revoke application authorization
#


@router.get('/revoke/github')
async def get_revoke_github(
    request: starlette.requests.Request,
):
    """Receive the initial revoke request from an EDI service, delete the user's token, and redirect
    back to client.
    """
    target_url = request.query_params.get('target')
    idp_token = request.query_params.get('idp_token')
    log.debug(f'revoke_github() target_url="{target_url}" idp_token="{idp_token}"')
    try:
        pass
        # revoke_grant(target_url, idp_token)
        # revoke_app_token(target_url, idp_token)
    except requests.RequestException:
        log.error('Revoke unsuccessful', exc_info=True)
        return util.redirect.client_error(target_url, 'Revoke unsuccessful')
    return util.redirect.redirect(target_url)


def revoke_app_token(_target_url, idp_token):
    revoke_response = requests.delete(
        f'https://api.github.com/applications/{Config.GITHUB_CLIENT_ID}/token',
        auth=(Config.GITHUB_CLIENT_ID, Config.GITHUB_CLIENT_SECRET),
        headers={
            'Accept': 'application/vnd.github+json',
            # 'Authorization': f'Bearer {github_client_secret}',
            'X-GitHub-Api-Version': '2022-11-28',
        },
        data=json.dumps({'access_token': idp_token}),
    )
    if revoke_response.status_code != starlette.status.HTTP_204_NO_CONTENT:
        raise requests.RequestException(revoke_response.text)


#
# Util
#


def is_error(
    request: starlette.requests.Request,
) -> bool:
    return request.query_params.get('error') is not None


def get_error_message(
    request: starlette.requests.Request,
) -> str:
    error_title = request.query_params.get('error', 'Unknown error')
    error_description = request.query_params.get('error_description', 'No description')
    error_uri = request.query_params.get('error_uri', 'No URI')
    return f'{error_title}: {error_description} ({error_uri})'


def fetch_user_avatar(avatar_url):
    response = requests.get(avatar_url)
    if response.ok:
        return response.content
    log.error(f'Failed to fetch user avatar: {response.status_code} {response.text}')
    return None
