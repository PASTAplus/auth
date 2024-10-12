import base64

import daiquiri
import fastapi
import starlette.requests
import starlette.responses

import db.iface
import pasta_ldap
import pasta_token as pasta_token_
import util
from config import Config

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

#
# Login
#


@router.get('/login/pasta')
async def login_pasta(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
):
    """Accept the initial login request from an EDI service and redirect to the
    LDAP login endpoint.
    """
    target = request.query_params.get('target')
    log.debug(f'login_pasta() target="{target}"')

    authorization = request.headers.get('Authorization')
    if authorization is None:
        return starlette.responses.Response(
            content='No authorization header in request', status_code=400
        )

    credentials = base64.b64decode(authorization[6:]).decode('utf-8')
    uid, password = credentials.split(':')

    if not pasta_ldap.bind(uid, password):
        return starlette.responses.Response(
            content=f'Authentication failed for user: {uid}', status_code=401
        )

    log.debug('login_pasta() - login successful')
    cname = util.get_dn_uid(uid)
    pasta_token = pasta_token_.make_pasta_token(uid=uid, groups=Config.VETTED)

    given_name, family_name = await util.split_full_name(cname)

    # Update DB
    identity_row = udb.create_or_update_profile_and_identity(
        given_name=given_name,
        family_name=family_name,
        idp_name='ldap',
        uid=uid,
        email=None,
        has_avatar=False,
        pasta_token=pasta_token,
    )

    # TODO: When clients are ready, remove the 418 Teapot response and cookie setting,
    # and move to handle the privacy policy acceptance internally in auth, as we already
    # do with the other IDPs.

    if not identity_row.profile.privacy_policy_accepted:
        # The 418 response is used to signal to the client that the privacy policy has
        # not yet been accepted. The client should redirect to the privacy policy
        # acceptance page, which will then redirect back to the target with the
        # pasta_token.
        return starlette.responses.Response(
            content='Privacy policy not yet accepted', status_code=418
        )

    # Redirect to the target URL with the authentication token
    # This is the normal flow when the privacy policy has already been accepted.
    # For LDAP, the pasta_token is set as a cookie, not a query parameter.
    response = starlette.responses.Response('Successful login')
    response.set_cookie('auth-token', pasta_token)
    return response
