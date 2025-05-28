import json
import logging
import pathlib

import daiquiri
import fastapi.testclient
import pytest_asyncio
import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

import db.base
import db.user
import main

DB_DRIVER = 'postgresql+psycopg'
DB_HOST = 'localhost'
DB_PORT = 5432
# DB_NAME = 'auth_test'
DB_NAME = 'auth'
DB_USER = 'auth'
DB_PW = 'testpw'
DB_POOL_SIZE = 10
DB_MAX_OVERFLOW = 20
DB_YIELD_ROWS = 1000
DB_CHUNK_SIZE = 10  # 8192
LOG_DB_QUERIES = False

HERE_PATH = pathlib.Path(__file__).parent.resolve()
DB_FIXTURE_JSON_PATH = HERE_PATH / 'tests/test_files/db_fixture.json'
# PROFILE_PATH = HERE_PATH / 'tests/test_files/profile.json'
# IDENTITY_PATH = HERE_PATH / 'tests/test_files/identity.json'

daiquiri.setup(
    level=logging.DEBUG,
    outputs=(
        daiquiri.output.File(HERE_PATH / 'test.log', 'a'),
        'stdout',
    ),
)

# @pytest.fixture(scope="session")
# def anyio_backend():
#     """Support async tests for FastAPI"""
#     return "asyncio"


@pytest_asyncio.fixture(scope='session')
async def db_engine():
    """Create an async Postgres DB engine for each test session. Ensure that all tables are
    created."""
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
            await conn.run_sync(lambda sync_conn: db.base.Base.metadata.create_all(bind=sync_conn))
        yield async_engine
    finally:
        await async_engine.dispose()


@pytest_asyncio.fixture(scope='session')
async def db_session(db_engine):
    """Create a fresh async Postgres DB session for each test session.
    The session is rolled back regardless of success or failure.
    """
    AsyncSessionFactory = sqlalchemy.ext.asyncio.async_sessionmaker(
        bind=db_engine,
        autocommit=False,
        autoflush=False,
    )
    async with AsyncSessionFactory() as async_session:
        try:
            yield async_session
        finally:
            await async_session.rollback()
            await async_session.close()


@pytest_asyncio.fixture(scope='session')
async def pop_session(db_session):
    """Create a populated async Postgres DB session for each test session.
    The database is populated with data from the JSON DB fixture file.
    """
    fixture_dict = json.loads(DB_FIXTURE_JSON_PATH.read_text())
    table_to_class_dict = {
        mapper.local_table.name: mapper.class_ for mapper in db.base.Base.registry.mappers
    }
    for table_name, rows in fixture_dict.items():
        assert table_name in db.base.Base.metadata.tables, f'Table not found: {table_name}'
        print(f'Importing {table_name}...')
        cls = table_to_class_dict[table_name]
        for row in rows:
            new_row = cls(**row)
            db_session.add(new_row)
    await db_session.flush()
    yield db_session


@pytest_asyncio.fixture(scope='session')
async def udb(db_session):
    """Create a UserDb instance for the test session."""
    yield db.user.UserDb(db_session)


@pytest_asyncio.fixture(scope='session')
async def pop_udb(pop_session):
    """Create a populated UserDb instance for the test session."""
    yield db.user.UserDb(pop_session)


@pytest_asyncio.fixture(scope='function')
async def client(db_session):
    """Create a test client for the FastAPI app."""
    with fastapi.testclient.TestClient(main.app) as client:
        yield client


@pytest_asyncio.fixture(scope='function')
async def profile_row(pop_udb):
    yield await pop_udb.get_profile('EDI-900e4dcb0c224dcda973ff3cb60a0d53')


# @pytest_asyncio.fixture(scope='function')
# def token(edi_id=None):
#     token = PastaToken()
#     token.system = Config.SYSTEM
#     token.uid = uid
#     token.groups = groups
#     private_key = pasta_crypto.import_key(Config.PRIVATE_KEY_PATH)
#     log.debug(f'Creating token: {token.to_string()}')
#     auth_token = pasta_crypto.create_auth_token(private_key, token.to_string())
#     return auth_token


# Example on how to override a dependency injection in FastAPI.
# main.app.dependency_overrides[util.dependency.udb] = functools.partial(
#     udb_override, db_session_populated
# )


# @pytest.fixture(autouse=True)
# def disable_warnings():
#     """Globally suppress warnings during tests."""
#     with warnings.catch_warnings():
#         warnings.filterwarnings('ignore', category=DeprecationWarning)
#         warnings.filterwarnings('ignore', category=sqlalchemy.exc.SAWarning)
#         warnings.filterwarnings('ignore')
#         warnings.simplefilter('ignore')
#         yield
