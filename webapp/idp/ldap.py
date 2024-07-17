import base64

import daiquiri
import fastapi
import starlette.requests
import starlette.responses

import pasta_ldap
import pasta_token as pasta_token_
import user_db
import util
from config import Config
import starlette.responses
import starlette.requests

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
        return f'No authorization header in request', 400

    credentials = base64.b64decode(authorization[6:]).decode('utf-8')
    uid, password = credentials.split(':')

    if not pasta_ldap.bind(uid, password):
        return f'Authentication failed for user: {uid}', 401

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

    # Redirect to privacy policy accept page if user hasn't accepted it yet
    # if not identity_row.profile.privacy_policy_accepted:
    #     return util.redirect(
    #         '/auth/accept',
    #         target=target,
    #         pasta_token=identity_row.pasta_token,
    #         urid=identity_row.profile.urid,
    #         full_name=identity_row.profile.full_name,
    #         email=identity_row.profile.email,
    #         uid=identity_row.uid,
    #         idp_name=identity_row.idp_name,
    #         idp_token=None,
    #     )

    if identity_row.profile.privacy_policy_accepted:
        response = starlette.responses.Response()
        response.set_cookie('auth-token', pasta_token)
        return response
    else:
        return 'I\'m a teapot, coffee is ready!', 418
