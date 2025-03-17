import daiquiri
import sqlalchemy.orm
import sqlalchemy.pool

import db.base
import db.user
from config import Config

"""Database interface.
"""


log = daiquiri.getLogger(__name__)


engine = sqlalchemy.create_engine(
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

# Use ./util/clear_database.py to drop all tables in the database.

# Create the tables in the database
db.base.Base.metadata.create_all(engine)

SessionLocal = sqlalchemy.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_udb():
    session = SessionLocal()
    try:
        return db.user.UserDb(session)
    finally:
        session.close()
