import daiquiri
import flask
import flask.blueprints
from flask import request

import webapp.pasta_crypto
import webapp.ui.forms
import webapp.user_db
import webapp.util

from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired


log = daiquiri.getLogger(__name__)
blueprint = flask.blueprints.Blueprint('index', __name__)

@blueprint.route("/", methods=["GET"])
def index():
    """The index page."""
    return flask.render_template("index.html")

@blueprint.route("/test", methods=["GET"])
def test():
    return flask.render_template(
        "accept.html",
        form=webapp.ui.forms.AcceptForm(),
        uid='test',
        target='test',
        idp='test',
        idp_token='test',
    )

