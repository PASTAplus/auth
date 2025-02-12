import sqlite3

import daiquiri
import fastapi
import sqlalchemy.event
import sqlalchemy.orm
import sqlalchemy.pool

import db.base
import db.user
from config import Config

"""Database interface.
"""


log = daiquiri.getLogger(__name__)

UserDb = db.user.UserDb

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

# engine = sqlalchemy.create_engine(
#     'sqlite:///' + Config.DB_PATH.as_posix(),
#     echo=Config.LOG_DB_QUERIES,
#     connect_args={
#         # Allow multiple threads to access the database
#         # This setup allows the SQLAlchemy engine to manage SQLite connections that can
#         # safely be shared across threads, mitigating the "SQLite objects created in a
#         # thread can only be used in that same thread" limitation.
#         # 'check_same_thread': False,
#     },
# )

# Use ./util/clear_database.py to drop all tables in the database.

# Create the tables in the database
db.base.Base.metadata.create_all(engine)

SessionLocal = sqlalchemy.orm.sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)


# Enable foreign key checking in SQLite
@sqlalchemy.event.listens_for(sqlalchemy.pool.Pool, 'connect')
def _on_connect(dbapi_con, _connection_record):
    if isinstance(dbapi_con, sqlite3.Connection):
        dbapi_con.execute('PRAGMA foreign_keys=ON')


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def udb(session: sqlalchemy.orm.Session = fastapi.Depends(get_session)):
    try:
        yield db.user.UserDb(session)
    finally:
        session.close()


def get_udb():
    session = SessionLocal()
    try:
        return db.user.UserDb(session)
    finally:
        session.close()
