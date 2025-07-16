import logging
import time

import daiquiri
import sqlalchemy.ext.asyncio
import sqlalchemy

from config import Config

"""Database interface.
"""


log = daiquiri.getLogger(__name__)

# The engine holds the database connection pool and states.
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


if Config.DB_QUERY_PROFILING:
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

# Session factory. Each request gets its own session object, which is created and closed within the
# request lifecycle.
AsyncSessionFactory = sqlalchemy.ext.asyncio.async_sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine
)

