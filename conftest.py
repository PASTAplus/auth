import json
import pathlib

import daiquiri
import fastapi.testclient
import pytest_asyncio
import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

import db.db_interface
import db.models.base
import main
import tests.edi_id
import tests.utils
import util.dependency

TEST_SERVER_BASE_URL = 'http://testserver/auth'


DB_DRIVER = 'postgresql+psycopg'
DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'auth_test'
DB_USER = 'auth'
DB_PW = 'testpw'
DB_POOL_SIZE = 10
DB_MAX_OVERFLOW = 20
DB_YIELD_ROWS = 1000
DB_CHUNK_SIZE = 10  # 8192
LOG_DB_QUERIES = False

HERE_PATH = pathlib.Path(__file__).parent.resolve()
DB_FIXTURE_JSON_PATH = HERE_PATH / 'tests/test_files/db_fixture.json'

log = daiquiri.getLogger(__name__)

# Fixtures: scope="session", autouse=True
#
# Fixtures with scope="session" and autouse=True run once per test session. They set up resources
# shared by all the tests. They are not directly referenced by the tests, and do not provide any
# test objects.


@pytest_asyncio.fixture(scope='session', autouse=True)
async def override_session_dependency(session_scope_populated_dbi):
    """Override the app's DbInterface dependency with the test-populated DbInterface."""
    # Note: dependency_overrides only works with functions that are wrapped in fastapi.Depends().
    main.app.dependency_overrides[util.dependency.dbi] = lambda: session_scope_populated_dbi
    yield
    main.app.dependency_overrides.clear()


# Fixture to override the system principal EDI-IDs in config.py.


@pytest_asyncio.fixture(scope='session', autouse=True)
async def override_system_principals():
    """Override the system principal EDI-IDs in config.py, to match those in db_fixture.json."""
    from config import Config

    Config.SERVICE_PROFILE_EDI_ID = tests.edi_id.SERVICE_ACCESS
    Config.PUBLIC_ACCESS_PROFILE_EDI_ID = tests.edi_id.PUBLIC_ACCESS
    Config.AUTHENTICATED_ACCESS_PROFILE_EDI_ID = tests.edi_id.AUTHENTICATED_ACCESS
    yield


# Fixtures: scope="session", autouse=False (the default)
#
# Fixtures with scope="session" and autouse=False are directly referenced by tests, but the object
# provided is generated only once, at the start of the test session.


@pytest_asyncio.fixture(scope='session')
async def test_engine():
    """Create an async Postgres DB engine for the test session.
    Ensure that all tables are created.
    """
    async_engine = sqlalchemy.ext.asyncio.create_async_engine(
        sqlalchemy.engine.URL.create(
            DB_DRIVER,
            host=DB_HOST,
            database=DB_NAME,
            username=DB_USER,
            password=DB_PW,
        ),
        echo=LOG_DB_QUERIES,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
    )
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: db.models.base.Base.metadata.create_all(bind=sync_conn)
            )
        yield async_engine
    finally:
        await async_engine.dispose()


@pytest_asyncio.fixture(scope='session')
async def test_session(test_engine):
    """Create a fresh async Postgres DB session for the test session.
    Roll back changes after each test while keeping the session scoped to the session.
    """
    AsyncSessionFactory = sqlalchemy.ext.asyncio.async_sessionmaker(
        bind=test_engine,
        autocommit=False,
        autoflush=False,
    )
    async with AsyncSessionFactory() as async_test_session:
        try:
            yield async_test_session
        except Exception as e:
            log.error(f'Error during test session: {e}')
            raise
        finally:
            await async_test_session.close()


@pytest_asyncio.fixture(scope='session')
async def populated_test_session(test_session):
    """Create a populated async Postgres DB session for the test session.
    The database is populated with data from the JSON DB fixture file.
    """
    fixture_dict = json.loads(DB_FIXTURE_JSON_PATH.read_text())
    table_to_class_dict = {
        mapper.local_table.name: mapper.class_ for mapper in db.models.base.Base.registry.mappers
    }
    for table_name, rows in fixture_dict.items():
        assert table_name in db.models.base.Base.metadata.tables, f'Table not found: {table_name}'
        # log.info(f'Importing {table_name}...')
        cls = table_to_class_dict[table_name]
        for row in rows:
            new_row = cls(**row)
            test_session.add(new_row)

    await test_session.flush()

    # Set the serial counter to start after the highest inserted ID
    for table_name, rows in fixture_dict.items():
        result = await test_session.execute(sqlalchemy.text(f'select max(id) from "{table_name}"'))
        max_id = result.scalars().first()
        # log.info(f'Serial sequence for {table_name}: {max_id}')
        await test_session.execute(
            sqlalchemy.text(
                'select setval(pg_get_serial_sequence(:table_name, :id_column), :max_id)'
            ),
            {'table_name': table_name, 'id_column': 'id', 'max_id': max_id},
        )

    await test_session.flush()
    yield test_session


@pytest_asyncio.fixture(scope='session')
async def dbi(test_session):
    """Create a DbInterface instance for the test session."""
    yield db.db_interface.DbInterface(test_session)


@pytest_asyncio.fixture(scope='session')
async def session_scope_populated_dbi(populated_test_session):
    """Create a populated DbInterface instance for the test session.
    Don't use this fixture directly; use populated_dbi instead, which wraps it in a savepoint.
    """
    yield db.db_interface.DbInterface(populated_test_session)

#
# Fixtures: scope="function", autouse=False (the default)
#

@pytest_asyncio.fixture(scope='function')
async def populated_dbi(session_scope_populated_dbi, populated_test_session):
    """Create a populated DbInterface instance for each test function.
    The instance is rolled back to a savepoint after each test, so that the database is reset to its
    initial state for the next test. The view of the test database is as seen from within the
    transaction.
    """
    transaction = await populated_test_session.begin_nested()
    try:
        yield session_scope_populated_dbi
    finally:
        await transaction.rollback()


#
# profile_row, token, and client fixtures for various profiles
#


# DB profile rows


@pytest_asyncio.fixture(scope='function')
async def service_profile_row(populated_dbi):
    """System profile: Service profile row"""
    yield await populated_dbi.get_profile('EDI-b2757fee12634ccca40d2d689f5c0543')


@pytest_asyncio.fixture(scope='function')
async def public_profile_row(populated_dbi):
    """System profile:Public Access profile row"""
    yield await populated_dbi.get_profile(tests.edi_id.PUBLIC_ACCESS)


@pytest_asyncio.fixture(scope='function')
async def authenticated_profile_row(populated_dbi):
    """System profile: Authenticated Access profile row"""
    yield await populated_dbi.get_profile(tests.edi_id.AUTHENTICATED_ACCESS)


@pytest_asyncio.fixture(scope='function')
async def john_profile_row(populated_dbi):
    """User profile: john@smith.com profile row"""
    yield await populated_dbi.get_profile(tests.edi_id.JOHN)


@pytest_asyncio.fixture(scope='function')
async def jane_profile_row(populated_dbi):
    """User profile: jane@brown.com profile row"""
    yield await populated_dbi.get_profile(tests.edi_id.JANE)


# Valid tokens


@pytest_asyncio.fixture(scope='function')
async def service_token(populated_dbi, service_profile_row):
    """System profile: Service token"""
    yield await tests.utils.make_jwt(populated_dbi, service_profile_row)


@pytest_asyncio.fixture(scope='function')
async def public_token(populated_dbi, public_profile_row):
    """System profile: Public Access token"""
    yield await tests.utils.make_jwt(populated_dbi, public_profile_row)


@pytest_asyncio.fixture(scope='function')
async def authenticated_token(populated_dbi, authenticated_profile_row):
    """System profile: Authenticated Access token"""
    yield await tests.utils.make_jwt(populated_dbi, authenticated_profile_row)


@pytest_asyncio.fixture(scope='function')
async def john_token(populated_dbi, john_profile_row):
    """User profile: john@smith.com token"""
    yield await tests.utils.make_jwt(populated_dbi, john_profile_row)


@pytest_asyncio.fixture(scope='function')
async def jane_token(populated_dbi, jane_profile_row):
    """User profile: jane@brown.com token"""
    yield await tests.utils.make_jwt(populated_dbi, jane_profile_row)


# Anon client


@pytest_asyncio.fixture(scope='function')
async def anon_client(populated_dbi):
    """Client that connects without providing a token"""
    yield fastapi.testclient.TestClient(main.app, base_url=TEST_SERVER_BASE_URL)


# Authenticated clients
#
# These clients are signed in to the indicated user profiles. They will pass a valid token when
# calling API endpoints.
#
# These fixtures are function scoped, and so are created and destroyed for each test function. Since
# the TestClient holds state, this ensures that each test starts with a fresh client, and avoids
# leaking client state between tests.


@pytest_asyncio.fixture(scope='function')
async def service_client(service_token):
    """System profile: Service client"""
    yield _create_test_client(service_token)


@pytest_asyncio.fixture(scope='function')
async def public_client(public_token):
    """System profile: Public Access client"""
    yield _create_test_client(public_token)


@pytest_asyncio.fixture(scope='function')
async def authenticated_client(authenticated_token):
    """System profile: Authenticated Access client"""
    yield _create_test_client(authenticated_token)


@pytest_asyncio.fixture(scope='function')
async def john_client(john_token):
    """User profile: john@smith.com client"""
    yield _create_test_client(john_token)


@pytest_asyncio.fixture(scope='function')
async def jane_client(jane_token):
    """User profile: jane@brown.com client"""
    yield _create_test_client(jane_token)


def _create_test_client(token):
    return fastapi.testclient.TestClient(
        main.app, cookies={'pasta_token': token}, base_url=TEST_SERVER_BASE_URL
    )
