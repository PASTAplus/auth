import daiquiri
import sqlalchemy.event
import sqlalchemy.orm
import sqlalchemy.pool
import sqlalchemy.ext.asyncio

import db.base
import db.user


# from fastapi_app import app
from config import Config

"""Database interface.
"""


log = daiquiri.getLogger(__name__)


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


# db.base.Base.metadata.create_all(engine)


# Session factory. Each request typically gets its own session object, which is created and closed
# within the request lifecycle.
AsyncSessionFactory = sqlalchemy.ext.asyncio.async_sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine
)




# sqlalchemy.event.listen(engine, 'connect', create_db_objects)

# Apply event listener to the synchronous engine
# @sqlalchemy.event.listens_for(async_engine.sync_engine, "connect")
# def on_connect(dbapi_connection, connection_record):
#     create_db_objects(dbapi_connection, connection_record)
