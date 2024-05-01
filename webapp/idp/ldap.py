import base64

import daiquiri
import flask
import flask.blueprints

import webapp.pasta_ldap
from webapp import pasta_token as pasta_token_
from webapp import user_db
from webapp import util
from webapp.config import Config

log = daiquiri.getLogger(__name__)
blueprint = flask.blueprints.Blueprint('ldap', __name__)

#
# Login
#


@blueprint.route('/auth/login/pasta', methods=['GET'])
def login_pasta():
    """Accept the initial login request from an EDI service and redirect to the
    LDAP login endpoint.
    """
    target = flask.request.args.get("target")
    log.debug(f'login_pasta() target="{target}"')

    authorization = flask.request.headers.get('Authorization')
    if authorization is None:
        return f'No authorization header in request', 400

    credentials = base64.b64decode(authorization[6:]).decode('utf-8')
    uid, password = credentials.split(':')

    if webapp.pasta_ldap.bind(uid, password):
        log.debug('login_pasta() - login successful')
        cname = util.get_dn_uid(uid)
        pasta_token = pasta_token_.make_pasta_token(uid=uid, groups=Config.VETTED)
        # Update DB
        udb = user_db.UserDb()
        udb.set_user(uid=uid, token=pasta_token, cname=cname)

        if udb.is_privacy_policy_accepted(uid=uid):
            response = flask.make_response()
            response.set_cookie('auth-token', pasta_token)
            return response
        else:
            return 'I\'m a teapot, coffee is ready!', 418
    else:
        return f'Authentication failed for user: {uid}', 401
