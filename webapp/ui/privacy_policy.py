import daiquiri
import flask
import flask.blueprints
from flask import request

import webapp.pasta_crypto
import webapp.ui.forms
import webapp.user_db
import webapp.util

log = daiquiri.getLogger(__name__)
blueprint = flask.blueprints.Blueprint('privacy_policy', __name__)


@blueprint.route("/auth/accept", methods=["GET"])
def accept_get():
    """Require the user to accept the privacy policy.

    This only serves the form. The form submission is handled by accept_post().
    """
    uid = request.args.get("uid")
    target = request.args.get("target")

    log.debug(f'Privacy policy accept form (GET): uid="{uid}" target="{target}"')

    udb = webapp.user_db.UserDb()

    if udb.get_user(uid) is None:
        return f'Unknown uid: {uid}', 400

    return flask.render_template(
        "accept.html",
        form=webapp.ui.forms.AcceptForm(),
        uid=uid,
        target=target,
        idp=request.args.get("idp"),
        idp_token=request.args.get("idp_token"),
    )


@blueprint.route("/auth/accept", methods=["POST"])
def accept_post():
    """Require the user to accept the privacy policy.

    If the policy is accepted, redirect back to the target with a new token.
    If the policy is not accepted, redirect back to the target with an error.
    """

    form = webapp.ui.forms.AcceptForm()
    is_accepted = form.accept.data
    uid = form.uid.data
    target = form.target.data

    log.debug(f'Privacy policy accept form (POST): uid="{uid}" target="{target}"')

    if not is_accepted:
        log.warn(f'Refused privacy policy: uid="{uid}" target="{target}"')
        return webapp.util.redirect(
            target,
            error="Login unsuccessful: Privacy policy not accepted",
        )

    log.debug(f'Accepted privacy policy: uid="{uid}" target="{target}"')

    udb = webapp.UserDb()
    udb.set_accepted(uid=uid)

    return webapp.util.redirect(
        target,
        token=udb.get_token(uid=uid),
        cname=udb.get_cname(uid=uid),
        idp=request.args.get("idp"),
        idp_token=request.args.get("idp_token"),
    )
