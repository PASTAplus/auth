import logging
import time

import daiquiri
import sqlalchemy.ext.asyncio
import sqlalchemy

from config import Config

import contextlib

import daiquiri
import fastapi

import util.dependency
import util.search_cache
import db.models.base


log = daiquiri.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(
    _app: fastapi.FastAPI,
):
    log.info('Application starting...')

    # The engine holds the database connection pool and state.
    async_engine = sqlalchemy.ext.asyncio.create_async_engine(
        sqlalchemy.engine.URL.create(
            Config.DB_DRIVER,
            host=Config.DB_HOST,
            database=Config.DB_NAME,
            username=Config.DB_USER,
            password=Config.DB_PW,
        ),
        echo=Config.LOG_DB_QUERIES,
        pool_size=Config.DB_POOL_SIZE,
        max_overflow=Config.DB_MAX_OVERFLOW,
    )

    # Session factory. Each request gets its own session object, which is created and closed within
    # the request lifecycle.
    AsyncSessionFactory = sqlalchemy.ext.asyncio.async_sessionmaker(
        autocommit=False, autoflush=False, bind=async_engine
    )

    # Pass the session factory to dependencies
    util.dependency.set_session_factory(AsyncSessionFactory)

    async with util.dependency.get_dbi() as dbi:
        # Create missing tables
        await dbi.session.run_sync(
            lambda sync_session: db.models.base.Base.metadata.create_all(bind=sync_session.bind)
        )
        # Initialize the profile and group search cache
        await util.search_cache.init_cache(dbi)
        # Update known package scopes
        await dbi.update_package_scopes()
        # Update known resource types
        await dbi.update_resource_types()
        # Update the roots of the resource tree
        await dbi.update_tree()

    if Config.DB_QUERY_PROFILING:
        await start_query_profiling(async_engine)

    # Run the app
    yield

    log.info('Application stopping...')
    await async_engine.dispose()


app = fastapi.FastAPI(lifespan=lifespan)


async def start_query_profiling(async_engine: sqlalchemy.ext.asyncio.AsyncEngine):
    log.info('Enabling query profiling')

    # Event listener to log query execution time
    @sqlalchemy.event.listens_for(async_engine.sync_engine, 'before_cursor_execute')
    def before_cursor_execute(_conn, _cursor, _statement, _parameters, context, _executemany):
        context._query_start_time = time.time()
        # logging.info(f'Starting query: {statement}')

    @sqlalchemy.event.listens_for(async_engine.sync_engine, 'after_cursor_execute')
    def after_cursor_execute(_conn, _cursor, statement, parameters, context, _executemany):
        total_time = time.time() - context._query_start_time
        logging.info(f'Query: {statement}')
        logging.info(f'Parameters: {parameters}')
        logging.info(f'Completed in {total_time:.2f} seconds')
