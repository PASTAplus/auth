import json

import daiquiri
import fastapi
import requests
import starlette.requests
import starlette.status

import db.iface

import util.avatar
import util.filesystem
import util.old_token
import util.pasta_crypto
import util.pasta_jwt
import util.pasta_ldap
import util.pretty
import util.search_cache
import util.template
import util.utils

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

    return util.utils.redirect_to_idp(
        Config.GITHUB_AUTH_ENDPOINT,
        'github',
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
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
):
    login_type, target_url = util.utils.unpack_state(request.query_params.get('state'))
    log.debug(f'callback_github() login_type="{login_type}" target_url="{target_url}"')

    if is_error(request):
        log.error(get_error_message(request))
        return util.utils.redirect_to_client_error(target_url, 'Login failed')

    code_str = request.query_params.get('code')
    if code_str is None:
        return util.utils.redirect_to_client_error(target_url, 'Login cancelled')

    try:
        token_response = requests.post(
            Config.GITHUB_TOKEN_ENDPOINT,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            },
            data=util.utils.build_query_string(
                client_id=Config.GITHUB_CLIENT_ID,
                client_secret=Config.GITHUB_CLIENT_SECRET,
                code=code_str,
                authorization_response=str(
                    util.utils.get_redirect_uri("github").replace_query_params(code=code_str)
                ),
                redirect_uri=util.utils.get_redirect_uri('github'),
                grant_type='authorization_code',
            ),
        )
    except requests.RequestException:
        log.error('Login unsuccessful', exc_info=True)
        return util.utils.redirect_to_client_error(target_url, 'Login unsuccessful')

    try:
        token_dict = token_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {token_response.text}', exc_info=True)
        return util.utils.redirect_to_client_error(target_url, 'Login unsuccessful')

    if 'error' in token_dict:
        log.error(f'Login unsuccessful: {token_dict["error"]}', exc_info=True)
        return util.utils.redirect_to_client_error(target_url, 'Login unsuccessful')

    try:
        userinfo_response = requests.get(
            Config.GITHUB_USER_ENDPOINT,
            headers={
                'Authorization': f'Bearer {token_dict["access_token"]}',
            },
        )
    except requests.RequestException:
        log.error('Login unsuccessful', exc_info=True)
        return util.utils.redirect_to_client_error(target_url, 'Login unsuccessful')

    try:
        user_dict = userinfo_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {userinfo_response.text}', exc_info=True)
        return util.utils.redirect_to_client_error(target_url, 'Login unsuccessful')

    # Fetch the avatar
    has_avatar = False
    try:
        avatar_img = get_user_avatar(user_dict['avatar_url'])
    except fastapi.HTTPException as e:
        log.error(f'Failed to fetch user avatar: {e.detail}')
    else:
        util.avatar.save_avatar(avatar_img, 'github', user_dict['html_url'])
        has_avatar = True

    log.debug('-' * 80)
    log.debug('github_callback() - login successful')
    util.pretty.log_dict(log.debug, 'token_dict', token_dict)
    util.pretty.log_dict(log.debug, 'user_dict', user_dict)
    log.debug('-' * 80)

    idp_uid = user_dict['html_url']
    if 'name' in user_dict and user_dict['name'] is not None:
        full_name = user_dict['name']
    elif 'login' in user_dict and user_dict['login'] is not None:
        full_name = user_dict['login']
    else:
        full_name = idp_uid

    return util.utils.handle_successful_login(
        request=request,
        udb=udb,
        login_type=login_type,
        target_url=target_url,
        full_name=full_name,
        idp_name='github',
        idp_uid=idp_uid,
        email=user_dict.get('email'),
        has_avatar=has_avatar,
        is_vetted=False,
    )


#
# Revoke application authorization
#


@router.get('/revoke/github')
async def get_revoke_github(
    request: starlette.requests.Request,
):
    """Receive the initial revoke request from an EDI service, delete the user's
    token, and redirect back to client.
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
        return util.utils.redirect_to_client_error(target_url, 'Revoke unsuccessful')

    return util.utils.redirect(target_url)


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


def get_user_avatar(avatar_url):
    response = requests.get(avatar_url)
    if not response.ok:
        raise fastapi.HTTPException(
            status_code=response.status_code, detail=response.text
        )
    return response.content
