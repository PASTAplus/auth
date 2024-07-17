import json

import daiquiri
import fastapi
import oauthlib.oauth2
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


@router.get('/auth/login/github')
async def login_github(
    request: starlette.requests.Request,
):
    """Accept the initial login request from an EDI service and redirect to the
    GitHub login endpoint.
    """
    target = request.query_params.get('target')
    log.debug(f'login_github() target="{target}"')

    return util.redirect(
        Config.GITHUB_AUTH_ENDPOINT,
        client_id=get_github_client_info(target=target)[0],
        redirect_uri=util.get_redirect_uri('github', target),
        scope='read:user',
        # prompt='consent',
        prompt='login',
    )


@router.get('/auth/login/github/callback/{target:path}')
async def login_github_callback(
    target,
    request: starlette.requests.Request,
    udb: user_db.UserDb = fastapi.Depends(user_db.udb),
):
    log.debug(f'login_github_callback() target="{target}"')

    if is_error(request):
        log.error(get_error_message(request))
        return util.redirect(target, error='Login failed')

    code_str = request.query_params.get('code')
    if code_str is None:
        return util.redirect(target, error='Login cancelled')

    github_client_id, github_client_secret = get_github_client_info(target=target)
    client = oauthlib.oauth2.WebApplicationClient(github_client_id)

    token_url, headers, body = client.prepare_token_request(
        Config.GITHUB_TOKEN_ENDPOINT,
        authorization_response=f'{util.get_redirect_uri("github", target)}?code={code_str}',
        code=code_str,
    )

    headers['Accept'] = 'application/json'

    try:
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(github_client_id, github_client_secret),
        )
    except requests.RequestException:
        log.error('Login unsuccessful', exc_info=True)
        return util.redirect(target, error=f'Login unsuccessful')

    try:
        token_dict = token_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {token_response.text}', exc_info=True)
        return util.redirect(target, error=f'Login unsuccessful')

    if 'error' in token_dict:
        log.error(f'Login unsuccessful: {token_dict["error"]}', exc_info=True)
        return util.redirect(target, error=f'Login unsuccessful')

    access_token = token_dict['access_token']
    headers['Authorization'] = f'token {access_token}'

    try:
        user_response = requests.get(url=Config.GITHUB_USER_ENDPOINT, headers=headers)
    except requests.RequestException:
        log.error('Login unsuccessful', exc_info=True)
        return util.redirect(target, error=f'Login unsuccessful')

    try:
        user_dict = user_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {token_response.text}', exc_info=True)
        return util.redirect(target, error=f'Login unsuccessful')

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


#
# Revoke application authorization
#


@router.get('/auth/revoke/github')
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
    github_client_id, github_client_secret = get_github_client_info(target=target)

    revoke_response = requests.delete(
        f'https://api.github.com/applications/{github_client_id}/token',
        auth=(github_client_id, github_client_secret),
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


def get_github_client_info(target: str) -> tuple:
    if target.startswith(Config.PORTAL_LOCALHOST):
        client_id, client_secret = (
            Config.GITHUB_CLIENT_ID_LOCALHOST,
            Config.GITHUB_CLIENT_SECRET_LOCALHOST,
        )
    elif target.startswith(Config.PORTAL_D):
        client_id, client_secret = (
            Config.GITHUB_CLIENT_ID_PORTAL_D,
            Config.GITHUB_CLIENT_SECRET_PORTAL_D,
        )
    elif target.startswith(Config.PORTAL_S):
        client_id, client_secret = (
            Config.GITHUB_CLIENT_ID_PORTAL_S,
            Config.GITHUB_CLIENT_SECRET_PORTAL_S,
        )
    elif target.startswith(Config.PORTAL):
        client_id, client_secret = (
            Config.GITHUB_CLIENT_ID_PORTAL,
            Config.GITHUB_CLIENT_SECRET_PORTAL,
        )
    elif target.startswith(Config.EZEML_D):
        client_id, client_secret = (
            Config.GITHUB_CLIENT_ID_EZEML_D,
            Config.GITHUB_CLIENT_SECRET_EZEML_D,
        )
    elif target.startswith(Config.EZEML_S):
        client_id, client_secret = (
            Config.GITHUB_CLIENT_ID_EZEML_S,
            Config.GITHUB_CLIENT_SECRET_EZEML_S,
        )
    elif target.startswith(Config.EZEML):
        client_id, client_secret = (
            Config.GITHUB_CLIENT_ID_EZEML,
            Config.GITHUB_CLIENT_SECRET_EZEML,
        )
    elif target.startswith(Config.WEB_X):
        client_id, client_secret = (
            Config.GITHUB_CLIENT_ID_WEB_X,
            Config.GITHUB_CLIENT_SECRET_WEB_X,
        )
    elif target.startswith(Config.WEB_D):
        client_id, client_secret = (
            Config.GITHUB_CLIENT_ID_WEB_D,
            Config.GITHUB_CLIENT_SECRET_WEB_D,
        )
    else:
        raise AssertionError(f'Unknown target: {target}')

    log.debug(f'get_github_client_info():')
    log.debug(
        f'target="{target}" -> client_id="{client_id}" client_secret="{client_secret}"'
    )
    return client_id, client_secret
