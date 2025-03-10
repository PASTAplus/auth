import daiquiri
import fastapi
import requests
import starlette.requests

import db.iface
import util
from config import Config

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

#
# Login
#


@router.get('/login/orcid')
async def login_orcid(
    request: starlette.requests.Request,
):
    """Accept the initial login request from an EDI service and redirect to the
    ORCID login endpoint.
    """
    login_type = request.query_params.get('login_type', 'client')
    target_url = request.query_params.get('target')
    log.debug(f'login_orcid() target_url="{target_url}"')

    return util.redirect_to_idp(
        Config.ORCID_AUTH_ENDPOINT,
        'orcid',
        login_type,
        target_url,
        client_id=Config.ORCID_CLIENT_ID,
        scope='/authenticate openid',
        prompt='login',
        response_type='code',
    )


@router.get('/callback/orcid')
async def callback_orcid(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
):
    login_type, target_url = util.unpack_state(request.query_params.get('state'))
    log.debug(f'callback_orcid() login_type="{login_type}" target_url="{target_url}"')

    code_str = request.query_params.get('code')
    if code_str is None:
        return util.redirect_to_client_error(target_url, 'Login cancelled')

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
        return util.redirect_to_client_error(target_url, 'Login unsuccessful')

    try:
        token_dict = token_response.json()
    except requests.JSONDecodeError:
        log.error(f'Login unsuccessful: {token_response.text}', exc_info=True)
        return util.redirect_to_client_error(target_url, 'Login unsuccessful')

    if is_error(token_dict):
        log.error(f'Login unsuccessful: {get_error(token_dict)}', exc_info=True)
        return util.redirect_to_client_error(target_url, 'Login unsuccessful')

    log.debug('-' * 80)
    log.debug('login_orcid_callback() - login successful')
    util.log_dict(log.debug, 'token_dict', token_dict)
    log.debug('-' * 80)

    return util.handle_successful_login(
        request=request,
        udb=udb,
        login_type=login_type,
        target_url=target_url,
        full_name=token_dict['name'],
        idp_name='orcid',
        uid=Config.ORCID_DNS + token_dict['orcid'],
        email=token_dict.get('email'),
        has_avatar=False,
        is_vetted=False,
    )


#
# Revoke application authorization
#


@router.get('/revoke/orcid')
async def revoke_orcid(
    request: starlette.requests.Request,
):
    target_url = request.query_params.get('target')
    uid = request.query_params.get('uid')
    idp_token = request.query_params.get('idp_token')
    util.log_dict(
        log.debug,
        'revoke_orcid()',
        {
            'target_url': target_url,
            'uid': uid,
            'idp_token': idp_token,
        },
    )
    return util.redirect(target_url)


#
# Util
#


def is_error(token_dict):
    return 'error' in token_dict


def get_error(token_dict):
    return f'{token_dict["error"]}: {token_dict["error_description"]}'
