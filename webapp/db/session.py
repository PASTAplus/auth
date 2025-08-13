import logging
import time

import daiquiri
import sqlalchemy.ext.asyncio

from config import Config

"""Database interface.
"""

log = daiquiri.getLogger(__name__)

# Global variable to hold the engine instance
_async_engine = None

def get_async_engine():
    """Get the async engine instance, creating it if it doesn't exist."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_default_async_engine()
    return _async_engine

def set_async_engine(engine):
    """Set a custom async engine (useful for testing)."""
    global _async_engine
    _async_engine = engine

def create_default_async_engine():
    """Create the default async engine with production configuration."""
    engine = sqlalchemy.ext.asyncio.create_async_engine(
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
        _setup_query_profiling(engine)

    return engine

def _setup_query_profiling(engine):
    """Setup query profiling event listeners."""
    log.info('Enabling query profiling')

    @sqlalchemy.event.listens_for(engine.sync_engine, 'before_cursor_execute')
    def before_cursor_execute(_conn, _cursor, _statement, _parameters, context, _executemany):
        context._query_start_time = time.time()

    @sqlalchemy.event.listens_for(engine.sync_engine, 'after_cursor_execute')
    def after_cursor_execute(_conn, _cursor, statement, parameters, context, _executemany):
        total_time = time.time() - context._query_start_time
        logging.info(f'Query: {statement}')
        logging.info(f'Parameters: {parameters}')
        logging.info(f'Completed in {total_time:.2f} seconds')

# Session factory using the engine getter
def get_session_factory():
    """Get a session factory bound to the current engine."""
    return sqlalchemy.ext.asyncio.async_sessionmaker(
        autocommit=False, autoflush=False, bind=get_async_engine()
    )
