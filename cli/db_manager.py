#!/usr/bin/env python

"""Manage DB schema for use with the app.

This script provides commands to create, drop, or clear objects in the database schema.

Create: Creates all the persistent objects in the database, such as tables, functions, and triggers.
Also creates the system profiles and groups. These are currently the Service, Public and
Authenticated profiles, and the Vetted group.

Drop: Drops all the persistent objects in the database, such as tables, functions, and triggers.

Clear: Clears the tables of user data, but keeps system profiles and groups, and the schema,
unmodified.
"""
import argparse
import asyncio
import logging
import pathlib
import sys

import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio
from sqlalchemy.exc import SQLAlchemyError

BASE_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((BASE_PATH / 'webapp').as_posix())

import db.models.base
import db.models.group
import db.session
import db.models.profile
import db.db_interface
import util.avatar
import util.dependency

from config import Config

log = daiquiri.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--debug', help='Debug level logging')
    parser.add_argument(
        '--test',
        action='store_true',
        help='Use the test database configuration instead of the production one',
    )
    subparsers = parser.add_subparsers(dest='command', help='Actions')
    subparsers.add_parser('create', help='Create database tables and objects')
    subparsers.add_parser('drop', help='Drop database tables and objects')
    subparsers.add_parser('clear', help='Clear user data from tables but keep schema unmodified')
    subparsers.add_parser('clear-resources', help='Clear only resources and rules')
    subparsers.add_parser('update', help='Update ')
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

    action_str = {
        'create': 'Create all tables and other objects',
        'drop': 'Drop all tables and other objects',
        'clear': 'Clear all user data from tables but keep schema unmodified',
        'update': 'Update all functions and triggers but keep tables and other objects unchanged',
        'clear-resources': 'Clear only resources and rules',
    }.get(args.command)
    answer_str = input(
        f'{action_str} in the {"TEST" if args.test else "PRODUCTION"} database? (y/n): '
    )
    if answer_str.lower() != 'y':
        log.info('Cancelled')
        return 1

    # Select DB configuration based on the --test flag
    db_config = {
        k: getattr(Config, f'{"TEST_" if args.test else ""}{k}')
        for k in (
            'DB_DRIVER',
            'DB_HOST',
            'DB_NAME',
            'DB_USER',
            'DB_PW',
            'LOG_DB_QUERIES',
            'DB_POOL_SIZE',
            'DB_MAX_OVERFLOW',
        )
    }

    # The engine holds the database connection pool and states.
    async_engine = sqlalchemy.ext.asyncio.create_async_engine(
        sqlalchemy.engine.URL.create(
            db_config['DB_DRIVER'],
            host=db_config['DB_HOST'],
            database=db_config['DB_NAME'],
            username=db_config['DB_USER'],
            password=db_config['DB_PW'],
        ),
        echo=db_config['LOG_DB_QUERIES'],
        pool_size=db_config['DB_POOL_SIZE'],
        max_overflow=db_config['DB_MAX_OVERFLOW'],
    )

    AsyncSessionFactory = sqlalchemy.ext.asyncio.async_sessionmaker(
        autocommit=False, autoflush=False, bind=async_engine
    )

    async with AsyncSessionFactory() as session:
        # The begin() context manager handles the session lifecycle, including committing or rolling
        # back transactions and closing the session.
        async with session.begin():
            dbi = db.db_interface.DbInterface(session)
            if args.command == 'create':
                await create_db(dbi)
            elif args.command == 'drop':
                await drop_tables_with_cascade(dbi)
                # await drop_tables_by_metadata(dbi)
            elif args.command == 'clear':
                await clear_db(dbi)
            elif args.command == 'clear-resources':
                await clear_resources(dbi)
            elif args.command == 'update':
                await update_functions_and_triggers(dbi)
            else:
                log.error(f'Unknown command: {args.command}')
                return 1
            await session.commit()

    log.info('Success!')
    return 0


#
# Create
#


async def create_db(dbi):
    await _create_tables(dbi)
    await _create_system_profiles(dbi)
    await _create_system_groups(dbi)
    await update_functions_and_triggers(dbi)


async def update_functions_and_triggers(dbi):
    await _create_function_get_resource_descendants(dbi)
    await _create_function_get_resource_ancestors(dbi)
    await _create_sync_triggers(dbi)
    await _create_search_package_scopes_trigger(dbi)
    await _create_search_resource_type_trigger(dbi)
    await _create_search_root_resource_trigger(dbi)


async def _create_tables(dbi):
    await dbi.session.run_sync(
        lambda sync_session: db.models.base.Base.metadata.create_all(bind=sync_session.bind)
    )
    await dbi.flush()


async def _create_system_profiles(dbi):
    """Create the system profiles for the Public and Authenticated profiles. This is a no-op for
    profiles that already exist.
    """
    for edi_id, common_name, avatar_path in (
        (
            Config.SERVICE_EDI_ID,
            Config.SERVICE_NAME,
            Config.SERVICE_AVATAR_PATH,
        ),
        (
            Config.PUBLIC_EDI_ID,
            Config.PUBLIC_NAME,
            Config.PUBLIC_AVATAR_PATH,
        ),
        (
            Config.AUTHENTICATED_EDI_ID,
            Config.AUTHENTICATED_NAME,
            Config.AUTHENTICATED_AVATAR_PATH,
        ),
    ):
        await dbi.create_profile(
            common_name=common_name,
            has_avatar=True,
            edi_id=edi_id,
        )
        util.avatar.init_system_avatar(edi_id, avatar_path)


async def _create_system_groups(dbi):
    """Create the system groups, currently just the Vetted group."""
    for owner_edi_id, group_edi_id, name, description, avatar_path in (
        (
            Config.SERVICE_EDI_ID,
            Config.VETTED_GROUP_EDI_ID,
            Config.VETTED_GROUP_NAME,
            Config.VETTED_GROUP_DESCRIPTION,
            Config.VETTED_GROUP_AVATAR_PATH,
        ),
    ):
        profile_row = await dbi.get_profile(owner_edi_id)
        await dbi.create_group(profile_row, name, description, group_edi_id)


async def _create_function_get_resource_descendants(dbi):
    """Create a function to get the resource tree starting from a given resource ID."""
    await dbi.execute(
        sqlalchemy.text(
            """
            create or replace function get_resource_descendants(node_ids integer[])
            returns table(id integer, label varchar, type varchar, parent_id integer)
            language plpgsql
            as $body$
            begin
                return query
                with recursive resource_tree as (
                    select r.id, r.label, r.type, r.parent_id
                    from resource r
                    where r.id = any(node_ids)
                    union all
                    select r.id, r.label, r.type, r.parent_id
                    from resource r
                    inner join resource_tree rt on r.parent_id = rt.id
                )
                select * from resource_tree;
            end;
            $body$;
            """
        )
    )


async def _create_function_get_resource_ancestors(dbi):
    """Create a function to get all ancestors of a list of resources in the tree."""
    await dbi.execute(
        sqlalchemy.text(
            """
            create or replace function get_resource_ancestors(node_ids integer[])
            returns table(id integer, label varchar, type varchar, parent_id integer)
            language plpgsql
            as $body$
            begin
                return query
                with recursive parent_tree as (
                    select r.id, r.label, r.type, r.parent_id
                    from resource r
                    where r.id = any(node_ids)
                    union all
                    select r.id, r.label, r.type, r.parent_id
                    from resource r
                    inner join parent_tree pt on r.id = pt.parent_id
                )
                select * 
                from parent_tree pt2
                where pt2.id != all(node_ids);
            end;
            $body$;
            """
        )
    )


async def _create_sync_triggers(dbi):
    """Create triggers to track table changes for synchronization with in-memory caches."""
    # Create trigger function. This function is called by the triggers to update the sync table.
    # A row for the given table name is created if it does not exist, or updated if it does.
    # In both cases, the updated timestamp is set to the current datetime.
    await dbi.execute(
        sqlalchemy.text(
            """
            create or replace function sync_trigger_func()
            returns trigger
            language plpgsql
            as $body$
            begin
                -- raise log 'Sync trigger for table: %', TG_TABLE_NAME;

                insert into sync (name, updated)
                values (TG_TABLE_NAME, now())
                on conflict (name)
                do update set updated = excluded.updated;

                return null;
            end;
            $body$;
            """
        )
    )
    # Create triggers for each table. We use 'for each statement' triggers, which triggers only once
    # per statement, not per row.
    for table in db.models.base.Base.metadata.tables.values():
        # Skip search tables, they are not used for synchronization. Also skip the sync table
        # itself.
        if table.name.startswith('search_') or table.name == 'sync':
            continue
        # We don't need unique names for each trigger here, but it can help with debugging,
        # maintenance, and database introspection.
        trigger_name = f"sync_{table.name}_trigger"
        await dbi.execute(
            sqlalchemy.text(
                # language=sql
                f"""
                drop trigger if exists {trigger_name} on "{table.name}";

                create trigger {trigger_name}
                after insert or update on "{table.name}"
                for each statement
                execute function sync_trigger_func();
                """
            )
        )


async def _create_search_package_scopes_trigger(dbi):
    """Create a trigger to update the search_package_scope table with any new scope when a package
    resource is created or updated, with label matching the package scope.identifier.revision
    pattern.
    """
    await dbi.execute(
        sqlalchemy.text(
            """
            create or replace function search_package_scopes_trigger_func()
            returns trigger
            language plpgsql
            as $body$
            begin
                if new.type = 'package' and new.label ~ '^[^.]+\\.[0-9]+\\.[0-9]+$' then
                    insert into search_package_scope (scope)
                    values (split_part(new.label, '.', 1))
                    on conflict (scope) do nothing;
                end if;

                return null;
            end;
            $body$;
            """
        )
    )
    await dbi.execute(
        sqlalchemy.text(
            # language=sql
            """
            drop trigger if exists search_package_scopes_trigger on resource;

            create trigger search_package_scopes_trigger
            after insert or update on resource
            for each row
            execute function search_package_scopes_trigger_func();
            """
        )
    )


async def _create_search_resource_type_trigger(dbi):
    """Create a trigger to update the search_resource_type table with any new resource type when a
    non-package root resource is created or updated.
    """
    await dbi.execute(
        sqlalchemy.text(
            """
            create or replace function search_resource_type_trigger_func()
            returns trigger
            language plpgsql
            as $body$
            begin
                if new.parent_id is null and new.type != 'package' then
                    insert into search_resource_type (type)
                    values (new.type)
                    on conflict (type) do nothing;
                end if;
                return null;
            end;
            $body$;
            """
        )
    )
    await dbi.execute(
        sqlalchemy.text(
            # language=sql
            """
            drop trigger if exists search_resource_type_trigger on resource;

            create trigger search_resource_type_trigger
            after insert or update on resource
            for each row
            execute function search_resource_type_trigger_func();
            """
        )
    )


async def _create_search_root_resource_trigger(dbi):
    """Create a trigger to update the search_root_resource table if a new root resource
    (parent_id=null) is created or updated.
    """
    await dbi.execute(
        sqlalchemy.text(
            """
            create or replace function search_root_resource_trigger_func()
            returns trigger
            language plpgsql
            as $body$
            declare
                package_scope varchar;
                package_id integer;
                package_rev integer;
            begin
                if new.parent_id is null then
                    -- Initialize package variables
                    package_scope := null;
                    package_id := null;
                    package_rev := null;

                    -- If this is a package resource with the expected format, extract components
                    if new.type = 'package' and new.label ~ '^[^.]+\\.[0-9]+\\.[0-9]+$' then
                        package_scope := split_part(new.label, '.', 1);
                        package_id := cast(split_part(new.label, '.', 2) as integer);
                        package_rev := cast(split_part(new.label, '.', 3) as integer);
                    end if;
                      
                    insert into search_root_resource (
                        resource_id, label, type, package_scope, package_id, package_rev
                    )
                    values (
                        new.id, 
                        new.label, 
                        new.type, 
                        package_scope, 
                        package_id, 
                        package_rev
                    )
                    on conflict (resource_id) do update set
                        label = excluded.label,
                        type = excluded.type,
                        package_scope = excluded.package_scope,
                        package_id = excluded.package_id,
                        package_rev = excluded.package_rev;
                    end if;

                return null;
            end;
            $body$;
            """
        )
    )
    await dbi.execute(
        sqlalchemy.text(
            # language=sql
            """
            drop trigger if exists search_root_resource_trigger on resource;

            create trigger search_root_resource_trigger
            after insert or update on resource
            for each row
            execute function search_root_resource_trigger_func();
            """
        )
    )


#
# Drop
#


async def drop_tables_with_cascade(dbi):
    for table in list(reversed(db.models.base.Base.metadata.sorted_tables)):
        log.info(f'Dropping table with cascade: {table.name}')
        try:
            # If the database hangs here, make sure there are no active connections to the
            # database (e.g., if the webapp is running).
            await dbi.execute(sqlalchemy.text(f'drop table if exists "{table.name}" cascade'))
        except SQLAlchemyError as e:
            log.error(f'Failed to drop table {table.name}: {e}')


async def drop_tables_by_metadata(dbi):
    log.info(f'Dropping all tables by metadata')
    try:
        await dbi.session.run_sync(
            lambda sync_session: db.models.base.Base.metadata.drop_all(
                bind=sync_session.bind, checkfirst=True
            )
        )
    except SQLAlchemyError:
        log.error('Failed to drop all tables by metadata')


#
# Clear
#


async def clear_db(dbi):
    """Clear all user data from the tables, but keep the schema unmodified.
    System profiles and groups are not cleared.
    """
    for table in db.models.base.Base.metadata.sorted_tables:
        log.info(f'Clearing table: {table.name}')
        try:
            await dbi.execute(sqlalchemy.text(f'truncate table "{table.name}" cascade'))
        except SQLAlchemyError as e:
            log.error(f'Failed to clear table {table.name}: {e}')

    await _create_system_profiles(dbi)
    await _create_system_groups(dbi)


async def clear_resources(dbi):
    """Clear only resources and rules, but keep the schema and other data unmodified."""
    log.info('Clearing resources and rules')
    try:
        await dbi.execute(sqlalchemy.text('truncate table "rule" cascade'))
        await dbi.execute(sqlalchemy.text('truncate table "resource" cascade'))
    except SQLAlchemyError as e:
        log.error(f'Failed to clear resources and rules: {e}')


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
