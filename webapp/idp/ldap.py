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
def login_pasta(
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

    if pasta_ldap.bind(uid, password):
        log.debug('login_pasta() - login successful')
        cname = util.get_dn_uid(uid)
        pasta_token = pasta_token_.make_pasta_token(uid=uid, groups=Config.VETTED)
        # Update DB
        udb.set_user(uid=uid, token=pasta_token, cname=cname)

        if udb.is_privacy_policy_accepted(uid=uid):
            response = starlette.responses.Response()
            response.set_cookie('auth-token', pasta_token)
            return response
        else:
            return 'I\'m a teapot, coffee is ready!', 418
    else:
        return f'Authentication failed for user: {uid}', 401
