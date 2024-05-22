import daiquiri
import flask
import sqlalchemy.orm

import webapp.api.refresh_token
import webapp.api.user
import webapp.idp.github
import webapp.idp.google
import webapp.idp.ldap
import webapp.idp.microsoft
import webapp.idp.orcid
import webapp.ui.privacy_policy
import webapp.ui.index
import webapp.user_db
from webapp.config import Config

# HERE_PATH = pathlib.Path(__file__).parent.resolve()
#
# daiquiri.setup(
#     level=Config.LOG_LEVEL,
#     outputs=(
#         daiquiri.output.File(HERE_PATH / 'test.log'),
#         'stdout',
#     ),
# )

log = daiquiri.getLogger(__name__)

app = flask.Flask(__name__)
app.config.from_object(Config)

log.debug('sqlite://' + Config.DB_PATH.as_posix())

engine = sqlalchemy.create_engine(
    'sqlite://' + Config.DB_PATH.as_posix(),
    echo=Config.LOG_DB_QUERIES,
)
# webapp.user_db.Base.metadata.create_all(engine)
session_maker_fn = sqlalchemy.orm.sessionmaker(bind=engine)  # ()


# with app.app_context():
#     Base = sqlalchemy.orm.declarative_base()
    # webapp.user_db.Base.metadata.create_all(engine)


@app.before_request
def create_db_session():
    flask.g.session = session_maker_fn()


@app.teardown_request
def close_db_session(exception=None):
    if exception:
        log.exception('Exception:')
    flask.g.session.close()


app.register_blueprint(webapp.idp.github.blueprint)
app.register_blueprint(webapp.idp.google.blueprint)
app.register_blueprint(webapp.idp.ldap.blueprint)
app.register_blueprint(webapp.idp.microsoft.blueprint)
app.register_blueprint(webapp.idp.orcid.blueprint)
app.register_blueprint(webapp.api.refresh_token.blueprint)
app.register_blueprint(webapp.api.user.blueprint)
app.register_blueprint(webapp.ui.privacy_policy.blueprint)
app.register_blueprint(webapp.ui.index.blueprint)
