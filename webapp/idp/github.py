import json

import daiquiri
import fastapi
import requests
import starlette.requests

import pasta_token as pasta_token_
import user_db
import util
from config import Config

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

#
# Login
#


@router.get('/login/github')
async def login_github(
    request: starlette.requests.Request,
):
    """Accept the initial login request from an EDI service and redirect to the
    GitHub login endpoint.
    """
    target = request.query_params.get('target')
    log.debug(f'login_github() target="{target}"')

    return util.redirect_to_idp(
        Config.GITHUB_AUTH_ENDPOINT,
        'github',
        target,
        client_id=Config.GITHUB_CLIENT_ID,
        scope='read:user',
        prompt='consent',
        # prompt='login',
    )


@router.get('/callback/github')
async def callback_github(
    request: starlette.requests.Request,
    udb: user_db.UserDb = fastapi.Depends(user_db.udb),
):
    target = request.cookies.get('target')
    log.debug(f'callback_github() target="{target}"')

    if is_error(request):
        log.error(get_error_message(request))
        return util.redirect(target, error='Login failed')

    code_str = request.query_params.get('code')
    if code_str is None:
        return util.redirect(target, error='Login cancelled')

    try:
        token_response = requests.post(
            Config.GITHUB_TOKEN_ENDPOINT,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            },
            data=util.build_query_string(
                client_id=Config.GITHUB_CLIENT_ID,
                client_secret=Config.GITHUB_CLIENT_SECRET,
                code=code_str,
                authorization_response=str(
                    util.get_redirect_uri("github").replace_query_params(code=code_str)
                ),
                redirect_uri=util.get_redirect_uri('github'),
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
            Config.GITHUB_USER_ENDPOINT,
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

    # Fetch the avatar
    try:
        avatar = get_user_avatar(user_dict['avatar_url'])
    except fastapi.HTTPException as e:
        log.error(f'Failed to fetch user avatar: {e.detail}')
    else:
        util.save_avatar(avatar, 'github', user_dict['html_url'])

    log.debug('-' * 80)
    log.debug('github_callback() - login successful')
    util.log_dict(log.debug, 'token_dict', token_dict)
    util.log_dict(log.debug, 'user_dict', user_dict)
    log.debug('-' * 80)

    uid = user_dict['html_url']
    if 'name' in user_dict and user_dict['name'] is not None:
        full_name = user_dict['name']
    elif 'login' in user_dict and user_dict['login'] is not None:
        full_name = user_dict['login']
    else:
        full_name = uid

    pasta_token = pasta_token_.make_pasta_token(uid=uid, groups=Config.AUTHENTICATED)

    given_name, family_name = await util.split_full_name(full_name)

    # Update DB
    identity_row = udb.create_or_update_profile_and_identity(
        given_name=given_name,
        family_name=family_name,
        idp_name='github',
        uid=uid,
        email=user_dict.get('email'),
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


#
# Revoke application authorization
#


@router.get('/revoke/github')
async def revoke_github(
    request: starlette.requests.Request,
):
    """Receive the initial revoke request from an EDI service, delete the user's
    token, and redirect back to client.
    """
    target = request.query_params.get('target')
    idp_token = request.query_params.get('idp_token')
    log.debug(f'revoke_github() target="{target}" idp_token="{idp_token}"')

    try:
        pass
        # revoke_grant(target, idp_token)
        # revoke_app_token(target, idp_token)
    except requests.RequestException:
        log.error('Revoke unsuccessful', exc_info=True)
        return util.redirect(target, error='Revoke unsuccessful')

    return util.redirect(target)


def revoke_app_token(target, idp_token):
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

    if revoke_response.status_code != 204:
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
    response = requests.get(
        avatar_url,
    )
    if not response.ok:
        raise fastapi.HTTPException(
            status_code=response.status_code, detail=response.text
        )
    return response.content
