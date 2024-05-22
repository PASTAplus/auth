import logging
import pathlib

import daiquiri
import pytest
import sqlalchemy
import sqlalchemy.orm

import webapp.main
import webapp.user_db
from webapp.config import Config

HERE_PATH = pathlib.Path(__file__).parent.resolve()

daiquiri.setup(
    level=logging.DEBUG,
    outputs=(
        daiquiri.output.File(HERE_PATH / 'test.log'),
        "stdout",
    ),
)


@pytest.fixture(scope='session')
def db_engine():
    """Create a fresh DB in RAM for each test session."""
    # Use an in-memory SQLite database for tests
    engine = sqlalchemy.create_engine('sqlite:///:memory:')
    # Create all tables
    webapp.user_db.Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Start a new DB session"""
    with db_engine.connect() as conn:
        with conn.begin() as tran:
            yield sqlalchemy.orm.sessionmaker(bind=conn)()
            tran.rollback()


# @pytest.fixture
# def db_session(db_engine):
#     """Start a new session for each test function."""
#     connection = db_engine.connect()
#     transaction = connection.begin()
#     session = sqlalchemy.orm.sessionmaker(bind=connection)()
#
#     yield session
#
#     session.close()
#     transaction.rollback()
#     connection.close()


@pytest.fixture
def user_db(db_session):
    return webapp.user_db.UserDb(db_session)


@pytest.fixture
def client():
    with webapp.main.app.test_client() as client:
        with webapp.main.app.app_context():
            yield client
