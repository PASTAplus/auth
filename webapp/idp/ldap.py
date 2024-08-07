import base64
import urllib.parse

import daiquiri
import fastapi
import starlette.requests
import starlette.responses

import pasta_ldap
import pasta_token as pasta_token_
import user_db
import util
from config import Config

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

#
# Login
#


@router.get('/auth/login/pasta')
async def login_pasta(
    request: starlette.requests.Request,
    udb: user_db.UserDb = fastapi.Depends(user_db.udb),
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
        pasta_token=pasta_token,
    )

    # TODO: When clients are ready, remove the 418 Teapot response and cookie setting,
    # and move to handle the privacy policy acceptance internally in auth, as we already
    # do with the other IDPs.

    if not identity_row.profile.privacy_policy_accepted:
        response = starlette.responses.Response(
            content='Privacy policy not yet accepted', status_code=418
        )
        # response.set_cookie('auth-token', pasta_token)
        return response

    # For LDAP, the pasta_token is set as a cookie, not a query parameter.
    response = starlette.responses.Response('Successful login')
    response.set_cookie('auth-token', urllib.parse.quote_plus(pasta_token))
    return response
