import json

import daiquiri
import flask
import flask.blueprints
import oauthlib.oauth2
import requests

from webapp import pasta_token as pasta_token_
from webapp import user_db
from webapp import util
from webapp.config import Config

log = daiquiri.getLogger(__name__)
blueprint = flask.blueprints.Blueprint('github', __name__)

#
# Login
#


@blueprint.route('/auth/login/github', methods=['GET'])
def login_github():
    """Accept the initial login request from an EDI service and redirect to the
    GitHub login endpoint.
    """
    target = flask.request.args.get("target")
    log.debug(f'login_github() target="{target}"')

    return util.redirect(
        Config.GITHUB_AUTH_ENDPOINT,
        client_id=get_github_client_info(target=target)[0],
        redirect_uri=f'{Config.CALLBACK_BASE_URL}/github/callback/{target}',
        scope='read:user',
        # prompt='consent',
        prompt='login',
    )


@blueprint.route('/auth/login/github/callback/<path:target>', methods=['GET'])
def login_github_callback(target):
    log.debug(f'login_github_callback() target="{target}"')

    if is_error():
        log.error(get_error_message())
        return util.redirect(target, error='Login failed')

    code_str = flask.request.args.get('code')
    if code_str is None:
        return util.redirect(target, error='Login cancelled')

    github_client_id, github_client_secret = get_github_client_info(target=target)
    client = oauthlib.oauth2.WebApplicationClient(github_client_id)

    token_url, headers, body = client.prepare_token_request(
        Config.GITHUB_TOKEN_ENDPOINT,
        authorization_response=flask.request.url,
        # redirect_url=flask.request.base_url,
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
    except requests.JSONDecodeError as e:
        log.error(f'Login unsuccessful: {token_response.text}', exc_info=True)
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
        cname = user_dict['name']
    elif 'login' in user_dict and user_dict['login'] is not None:
        cname = user_dict['login']
    else:
        cname = uid

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
            idp='github',
            idp_token=access_token,
        )

    # Finally, redirect to the target URL with the authentication token
    return util.redirect(
        target,
        token=pasta_token,
        cname=cname,
        idp='github',
        idp_token=access_token,
    )


#
# Revoke application authorization
#


@blueprint.route('/auth/revoke/github', methods=['GET'])
def revoke_github():
    """Receive the initial revoke request from an EDI service, delete the user's
    token, and redirect back to client.
    """
    target = flask.request.args.get("target")
    idp_token = flask.request.args.get('idp_token')
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
        # f'https://api.github.com/applications/{github_client_id}/grant',
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


def is_error() -> bool:
    return flask.request.args.get('error') is not None


def get_error_message() -> str:
    error_title = flask.request.args.get('error', 'Unknown error')
    error_description = flask.request.args.get('error_description', 'No description')
    error_uri = flask.request.args.get('error_uri', 'No URI')
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
