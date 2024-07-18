import re

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


@router.get('/auth/login/orcid')
async def login_orcid(
    request: starlette.requests.Request,
):
    """Accept the initial login request from an EDI service and redirect to the
    ORCID login endpoint.
    """
    target = request.query_params.get('target')
    log.debug(f'login_orcid() target="{target}"')
    return util.redirect(
        Config.ORCID_AUTH_ENDPOINT,
        client_id=Config.ORCID_CLIENT_ID,
        response_type='code',
        scope='/authenticate openid',
        redirect_uri=util.get_redirect_uri('orcid', util.urlenc(target)),
        prompt='login',
    )


@router.get('/auth/login/orcid/callback/{target:path}')
async def login_orcid_callback(
    target,
    request: starlette.requests.Request,
    udb: user_db.UserDb = fastapi.Depends(user_db.udb),
):
    # Hack to work around ORCID collapsing multiple slashes in the URL path, which breaks the target
    # URL. This adds any missing slash after the protocol.
    # E.g., https:/host/path -> https://host/path
    if m := re.match(r'(https?:/)([^/].*)', target, re.IGNORECASE):
        target = f'{m.group(1)}/{m.group(2)}'

    log.debug(f'login_orcid_callback() target="{target}"')

    code_str = request.query_params.get('code')
    if code_str is None:
        return util.redirect(target, error='Login cancelled')

    try:
        token_response = requests.post(
            Config.ORCID_TOKEN_ENDPOINT,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            },
            data=util.build_query_string(
                client_id=Config.ORCID_CLIENT_ID,
                client_secret=Config.ORCID_CLIENT_SECRET,
                grant_type='authorization_code',
                code=code_str,
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

    if is_error(token_dict):
        log.error(f'Login unsuccessful: {get_error(token_dict)}', exc_info=True)
        return util.redirect(target, error='Login unsuccessful')

    log.debug('-' * 80)
    log.debug('login_orcid_callback() - login successful')
    util.log_dict(log.debug, 'token_dict', token_dict)
    log.debug('-' * 80)

    cname = token_dict['name']
    uid = Config.ORCID_DNS + token_dict['orcid']

    pasta_token = pasta_token_.make_pasta_token(uid=uid, groups=Config.AUTHENTICATED)

    given_name, family_name = await util.split_full_name(cname)

    # Update DB
    identity_row = udb.create_or_update_profile_and_identity(
        given_name=given_name,
        family_name=family_name,
        idp_name='orcid',
        uid=uid,
        email=token_dict.get('email'),
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


@router.get('/auth/revoke/orcid')
async def revoke_orcid(
    request: starlette.requests.Request,
):
    target = request.query_params.get('target')
    uid = request.query_params.get('uid')
    idp_token = request.query_params.get('idp_token')
    util.log_dict(
        log.debug,
        'revoke_orcid()',
        {
            'target': target,
            'uid': uid,
            'idp_token': idp_token,
        },
    )
    return util.redirect(target)


#
# Util
#


def is_error(token_dict):
    return 'error' in token_dict


def get_error(token_dict):
    return f'{token_dict["error"]}: {token_dict["error_description"]}'
