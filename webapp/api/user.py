import daiquiri
import flask.blueprints
from flask import request

import webapp.pasta_crypto
from webapp import pasta_token as pasta_token_
from webapp.config import Config

log = daiquiri.getLogger(__name__)
blueprint = flask.blueprints.Blueprint('user', __name__)


