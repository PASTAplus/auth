import daiquiri
import flask.blueprints
from flask import request

import webapp.pasta_crypto
from webapp import pasta_token as pasta_token_
from webapp.config import Config

log = daiquiri.getLogger(__name__)
blueprint = flask.blueprints.Blueprint('refresh_token', __name__)


PUBLIC_KEY = webapp.pasta_crypto.import_key(Config.PUBLIC_KEY_PATH)
PRIVATE_KEY = webapp.pasta_crypto.import_key(Config.PRIVATE_KEY_PATH)


@blueprint.route("/auth/refresh", methods=["POST"])
def refresh_token():
    """Validate and refresh an authentication token.

    A refreshed token is a token that matches the original token's uid and
    groups but has a new TTL.
    """
    external_token = request.get_data(as_text=True)

    # Verify the token signature
    try:
        webapp.pasta_crypto.verify_auth_token(PUBLIC_KEY, external_token)
    except ValueError as e:
        msg = f"Attempted to refresh invalid token: {e}"
        log.error(msg)
        return msg, 401

    # Verify the token TTL
    token_obj = pasta_token_.PastaToken()
    token_obj.from_auth_token(external_token)
    if not token_obj.is_valid_ttl():
        msg = f"Attempted to refresh invalid token: Token has expired"
        log.error(msg)
        return msg, 401

    # Create the refreshed token
    token_obj = pasta_token_.PastaToken()
    token_obj.from_auth_token(external_token)
    token_obj.ttl = token_obj.new_ttl()
    return webapp.pasta_crypto.create_auth_token(PRIVATE_KEY, token_obj.to_string())
