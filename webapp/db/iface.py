import daiquiri
import sqlalchemy.event
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


def create_sync_trigger(dbapi_connection, _connection_record):
    """Create triggers to track table changes for synchronization with in-memory caches."""
    cursor = dbapi_connection.cursor()
    try:
        # Create trigger function. This function is called by the triggers to update the sync table.
        # A row for the given table name is created if it does not exist, or updated if it does.
        # In both cases, the updated timestamp is set to the current datetime.
        cursor.execute(
            """
            do $$
            begin
                if not exists (select 1 from pg_proc where proname = 'sync_trigger_func') then
                    create or replace function sync_trigger_func()
                    returns trigger
                    language plpgsql
                    as $body$
                    begin
                        RAISE NOTICE 'Sync trigger for table: %', TG_TABLE_NAME;
        
                        insert into sync (name, updated)
                        values (TG_TABLE_NAME, now())
                        on conflict (name)
                        do update set updated = excluded.updated;
                        
                        return null;
                    end;
                    $body$;
                end if;
            end;
            $$;
            """
        )

        # Create triggers for each table
        for trigger_name, table_name in (
            ("sync_trigger_collection", "collection"),
            ("sync_trigger_group", "\"group\""),
            ("sync_trigger_group_member", "group_member"),
            ("sync_trigger_identity", "identity"),
            ("sync_trigger_rule", "rule"),
            ("sync_trigger_profile", "profile"),
            ("sync_trigger_resource", "resource"),
        ):
            cursor.execute(
                f"""
                do $$
                begin
                    if not exists (select 1 from pg_trigger where tgname = '{trigger_name}') then
                        create trigger {trigger_name}
                        after insert or update on {table_name}
                        for each statement
                        execute function sync_trigger_func();
                    end if;
                end;
                $$;
                """
            )

        dbapi_connection.commit()
    finally:
        cursor.close()


sqlalchemy.event.listen(engine, 'connect', create_sync_trigger)


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
