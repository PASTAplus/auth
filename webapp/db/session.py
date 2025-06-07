import daiquiri
import sqlalchemy.ext.asyncio

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

# Session factory. Each request gets its own session object, which is created and closed within the
# request lifecycle.
AsyncSessionFactory = sqlalchemy.ext.asyncio.async_sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine
)
