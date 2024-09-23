import sqlite3

import daiquiri
import fastapi
import sqlalchemy.event
import sqlalchemy.orm
import sqlalchemy.pool

import config
import db.base
import db.user
import db.group


"""Database interface.
"""


log = daiquiri.getLogger(__name__)

# Bring types here for convenience
# Base = db.base.Base
UserDb = db.user.UserDb
# GroupDb = db.group.GroupDb

engine = sqlalchemy.create_engine(
    'sqlite:///' + config.Config.DB_PATH.as_posix(),
    echo=config.Config.LOG_DB_QUERIES,
    connect_args={
        # Allow multiple threads to access the database
        # This setup allows the SQLAlchemy engine to manage SQLite connections that can
        # safely be shared across threads, mitigating the "SQLite objects created in a
        # thread can only be used in that same thread" limitation.
        'check_same_thread': False,
    },
)

# TODO: Add some sort of switch for this
# Base.metadata.drop_all(engine)

# Create the tables in the database
db.base.Base.metadata.create_all(engine)

SessionLocal = sqlalchemy.orm.sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)


# Enable foreign key checking in SQlite
@sqlalchemy.event.listens_for(sqlalchemy.pool.Pool, "connect")
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


# def gdb(session: sqlalchemy.orm.Session = fastapi.Depends(get_session)):
#     try:
#         yield db.user.GroupDb(session)
#     finally:
#         session.close()

# def get_group_db():
#     db = group_db.SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# def gdb(session: group_db.sqlalchemy.orm.Session = group_db.fastapi.Depends(get_user_db)):
#     try:
#         yield group_db.GroupDb(session)
#     finally:
#         session.close()
