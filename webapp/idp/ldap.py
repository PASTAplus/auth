import base64
import binascii
import re

import daiquiri
import fastapi
import starlette.datastructures
import starlette.requests
import starlette.responses
import starlette.status

import util.dependency
import util.old_token
import util.pasta_ldap
import util.pasta_jwt

from config import Config

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

#
# Login
#


@router.get('/login/pasta')
async def get_login_pasta(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
):
    """Accept LDAP credentials, validate them against an external LDAP service, and
    return a response with cookie containing the old style token.

    NOTES:

    - This endpoint is not called by a browser. It is called from the server side of the
    web app (Portal and ezEML), so any information added to the response here will not
    make it to the client, and will not be acted on by the web app.

    - The server side checks for 200 response code and then pulls the token from the
    Set-Cookie header with key 'auth-token'. For the Portal, the token is then added
    to the Java Session.

    - Since calls to this endpoint is not initiated by browser, there's no opportunity
    to redirect back to Auth in order set a cookie in the browser.
    """
    target_url = request.query_params.get('target')
    log.debug(f'login_pasta() target_url="{target_url}"')

    try:
        ldap_dn, password = parse_authorization_header(request)
    except ValueError as e:
        return starlette.responses.Response(
            content=str(e), status_code=starlette.status.HTTP_400_BAD_REQUEST
        )

    dn_uid = get_ldap_uid(ldap_dn)

    if not util.pasta_ldap.bind(ldap_dn, password):
        return starlette.responses.Response(
            content=f'Authentication failed for user: {dn_uid}',
            status_code=starlette.status.HTTP_401_UNAUTHORIZED,
        )

    log.debug(f'login_pasta() - login successful: {ldap_dn}')

    identity_row = await udb.create_or_update_profile_and_identity(
        idp_name='ldap',
        idp_uid=ldap_dn,
        common_name=dn_uid,
        email=None,
        has_avatar=False,
    )

    # As described in the docstr, this response goes to the server side web app, so we create a
    # limited response that contains only the items checked for by the server.
    old_token_ = util.old_token.make_old_token(uid=ldap_dn, groups=Config.VETTED)
    pasta_token = await util.pasta_jwt.make_jwt(udb, identity_row, is_vetted=True)
    response = starlette.responses.Response('Login successful')
    response.set_cookie('auth-token', old_token_)
    response.set_cookie('pasta-token', pasta_token)
    return response


def get_ldap_uid(ldap_dn: str) -> str:
    dn_dict = {k.strip(): v.strip() for (k, v) in (part.split('=') for part in ldap_dn.split(','))}
    return dn_dict['uid']


def get_ldap_dn(dn_uid: str) -> str:
    return f'uid={dn_uid},o=EDI,dc=edirepository,dc=org'


def parse_authorization_header(
    request,
) -> tuple[str, str] | starlette.responses.Response:
    """Parse the Authorization header from a request and return (idp_uid, pw). Raise
    ValueError on errors.
    """
    auth_str = request.headers.get('Authorization')
    if auth_str is None:
        raise ValueError('No authorization header in request')
    if not (m := re.match(r'Basic\s+(.*)', auth_str)):
        raise ValueError(f'Invalid authorization scheme. Only Basic is supported: {auth_str}')
    encoded_credentials = m.group(1)
    try:
        decoded_credentials = base64.b64decode(encoded_credentials, validate=True).decode('utf-8')
        idp_uid, password = decoded_credentials.split(':', 1)
        return idp_uid, password
    except (ValueError, IndexError, binascii.Error) as e:
        raise ValueError(f'Malformed authorization header: {e}')


def format_authorization_header(idp_uid: str, password: str) -> str:
    assert ':' not in idp_uid
    assert ':' not in password
    return f'Basic {base64.b64encode(f"{idp_uid}:{password}".encode()).decode()}'
