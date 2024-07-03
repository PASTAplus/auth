import daiquiri
from flask import Flask, redirect, render_template, request
from flask_bootstrap import Bootstrap

from webapp import pasta_crypto
from webapp import pasta_token as pasta_token_
from webapp import util
from webapp.config import Config
from webapp.forms import AcceptForm
from webapp.idp import github
from webapp.idp import google
from webapp.idp import ldap
from webapp.idp import microsoft
from webapp.idp import orcid
from webapp.user_db import UserDb

log = daiquiri.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
bootstrap = Bootstrap(app)

PUBLIC_KEY = pasta_crypto.import_key(Config.PUBLIC_KEY)
PRIVATE_KEY = pasta_crypto.import_key(Config.PRIVATE_KEY)

app.register_blueprint(github.blueprint)
app.register_blueprint(google.blueprint)
app.register_blueprint(ldap.blueprint)
app.register_blueprint(microsoft.blueprint)
app.register_blueprint(orcid.blueprint)


@app.route("/auth/accept", methods=["GET"])
def accept_get():
    """Require the user to accept the privacy policy.

    This only serves the form. The form submission is handled by accept_post().
    """
    uid = request.args.get("uid")
    target = request.args.get("target")

    log.debug(f'Privacy policy accept form (GET): uid="{uid}" target="{target}"')

    udb = UserDb()

    if udb.get_user(uid) is None:
        return f'Unknown uid: {uid}', 400

    return render_template(
        "accept.html",
        form=AcceptForm(),
        uid=uid,
        target=target,
        idp=(request.args.get("idp")),
        idp_token=(request.args.get("idp_token")),
        sub=(request.args.get("sub")),
    )


@app.route("/auth/accept", methods=["POST"])
def accept_post():
    """Require the user to accept the privacy policy.

    If the policy is accepted, redirect back to the target with a new token.
    If the policy is not accepted, redirect back to the target with an error.
    """

    form = AcceptForm()
    is_accepted = form.accept.data
    uid = form.uid.data
    target = form.target.data

    log.debug(f'Privacy policy accept form (POST): uid="{uid}" target="{target}"')

    if not is_accepted:
        log.warn(f'Refused privacy policy: uid="{uid}" target="{target}"')
        return util.redirect(
            target,
            error="Login unsuccessful: Privacy policy not accepted",
        )

    log.debug(f'Accepted privacy policy: uid="{uid}" target="{target}"')

    udb = UserDb()
    udb.set_accepted(uid=uid)

    return util.redirect(
        target,
        token=udb.get_token(uid=uid),
        cname=udb.get_cname(uid=uid),
        idp=request.args.get("idp"),
        idp_token=request.args.get("idp_token"),
        sub=request.args.get("sub"),
    )


@app.route("/auth/show_me", methods=["GET"])
def show_me():
    uid = request.args["uid"]
    log.info(uid)
    return uid


@app.route("/auth/refresh", methods=["POST"])
def refresh_token():
    """Validate and refresh an authentication token.

    A refreshed token is a token that matches the original token's uid and
    groups but has a new TTL.
    """
    external_token = request.get_data(as_text=True)

    # Verify the token signature
    try:
        pasta_crypto.verify_auth_token(PUBLIC_KEY, external_token)
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
    return pasta_crypto.create_auth_token(PRIVATE_KEY, token_obj.to_string())
