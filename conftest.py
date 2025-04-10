import datetime
import functools
import json
import logging
import pathlib
import warnings

import daiquiri
import fastapi.testclient
import pytest
import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.orm

import db.iface
import db.user
import webapp.main
import webapp.db.iface
import webapp.db.base
import webapp.db
# from webapp.config import Config

app = fastapi.FastAPI()

HERE_PATH = pathlib.Path(__file__).parent.resolve()
PROFILE_PATH = HERE_PATH / 'tests/test_files/profile.json'
IDENTITY_PATH = HERE_PATH / 'tests/test_files/identity.json'

daiquiri.setup(
    level=logging.DEBUG,
    outputs=(
        daiquiri.output.File(HERE_PATH / 'test.log'),
        'stdout',
    ),
)


# @pytest.fixture(scope="session")
# def anyio_backend():
#     """Support async tests for FastAPI"""
#     return "asyncio"


@pytest.fixture(scope='session')
def db_engine():
    """Create a fresh DB in RAM for each test session."""
    # Use an in-memory SQLite database for tests
    engine = sqlalchemy.create_engine(
        'sqlite:///:memory:',
        echo=False,
        connect_args={
            'check_same_thread': False,
        },
    )
    # Create all tables
    webapp.db.base.Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Start a new DB session"""
    # The connection is pulled from the pool of existing connections
    with db_engine.connect() as conn:
        with conn.begin() as tran:
            yield sqlalchemy.orm.sessionmaker(bind=conn)()
            tran.rollback()


@pytest.fixture
def db_session_populated(db_session):
    #     "id": 4,
    #     "edi_id": "EDI-e851e1a4b19c4b78992455807fe79534",
    #     "given_name": "Given1",
    #     "family_name": "Family1",
    #     "email": "testuser@github.com",
    #     "privacy_policy_accepted": 1,
    #     "privacy_policy_accepted_date": "2024-07-17 22:41:09.699175"
    profile_list = json.loads(PROFILE_PATH.read_text())
    #     "id": 4,
    #     "profile_id": 4,
    #     "idp_name": "github",
    #     "uid": "https://github.com/testuser",
    #     "email": "testuser@github.com",
    #     "pasta_token": "aHR0cHM6Ly9naXRodWIuY29tL3JvZ2VyZGFobCpodHRwczovL3Bhc3RhLmVkaXJlcG9zaXRvcnkub3JnL2F1dGhlbnRpY2F0aW9uKjE3MjE4MTAwNjUyODcqYXV0aGVudGljYXRlZA==-T57+LlHbgyk1OGn4kJy+O4MSqBMnvbYPUa5g+QlE5Mnhpt8OhRdjOq7YhQ3NRJ4oHfhnrZERRsYQ2NP5BD6oW4LXLHKfUG8mX/h6aOrzuYiyqtvGHnDqZ5pwxtOjTH111HjaI1pPbK6xysHfen8iku4UTETbywMzdSozNiwVm03aeFUEIu+aKaaTjrjZ9GGCKdYt6SLUOdiZV2KBFWdibORZHnWL9jblde2FOlvnjokYhifi2UHqms6NJCHefFGcWfvKnAe4fYctpUcyfNt96i1fgx1WWozoCOXhOpcHCwJvAAmKFrem46EWALtaX0g+vMjFzzxBB61OB8rqGaUUhA==",
    #     "first_auth": "2024-07-17 22:41:07.246722",
    #     "last_auth": "2024-07-23 18:34:25.518037"
    identity_list = json.loads(IDENTITY_PATH.read_text())
    for profile_dict in profile_list:
        # webapp.util.pp(profile_dict)
        accepted_date = profile_dict['privacy_policy_accepted_date']
        profile_row = db.user.Profile(
            edi_id=profile_dict['edi_id'],
            given_name=profile_dict['given_name'],
            family_name=profile_dict['family_name'],
            email=profile_dict['email'],
            privacy_policy_accepted=profile_dict['privacy_policy_accepted'],
            privacy_policy_accepted_date=(_from_iso(accepted_date)),
        )
        db_session.add(profile_row)

    for identity_dict in identity_list:
        identity_row = db.user.Identity(
            profile_id=identity_dict['profile_id'],
            idp_name=identity_dict['idp_name'],
            uid=identity_dict['uid'],
            email=identity_dict['email'],
            pasta_token=identity_dict['pasta_token'],
            first_auth=(_from_iso(identity_dict['first_auth'])),
            last_auth=(_from_iso(identity_dict['last_auth'])),
        )
        db_session.add(identity_row)

    db_session.commit()

    yield db_session




@pytest.fixture
def user_db_populated(db_session_populated):
    return db.iface.UserDb(db_session_populated)


def udb_override(session: sqlalchemy.orm.Session):
    try:
        yield db.iface.UserDb(session)
    finally:
        session.close()


@pytest.fixture
def client(db_session_populated):
    # noinspection PyUnresolvedReferences
    webapp.main.app.dependency_overrides[util.dependency.udb] = functools.partial(
        udb_override, db_session_populated
    )
    with fastapi.testclient.TestClient(webapp.main.app) as client:
        yield client


@pytest.fixture(autouse=True)
def disable_warnings():
    """Disable: SAWarning: transaction already deassociated from connection"""
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=sqlalchemy.exc.SAWarning)
        yield


def _from_iso(iso_date_str):
    return (
        datetime.datetime.fromisoformat(iso_date_str)
        if isinstance(iso_date_str, str)
        else None
    )
