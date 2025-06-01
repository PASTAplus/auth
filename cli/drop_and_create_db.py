#!/usr/bin/env python

"""Drop all tables in the database.
"""

import asyncio
import logging
import pathlib
import sys

import daiquiri
import sqlalchemy.exc

ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((ROOT_PATH / 'webapp').as_posix())

import db.base
import db.iface
import db.user
import util.avatar
import db.profile
import util.dependency

from config import Config

log = daiquiri.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    answer_str = input(
        'Are you sure you want to drop all tables and other objects in the database? (y/n): '
    )
    if answer_str.lower() != 'y':
        log.info('Cancelled')
        return 1

    async with util.dependency.get_session() as session:
        await drop_and_create_tables(session)
        await create_function_get_resource_tree(session)
        await create_function_get_resource_parents(session)
        await create_sync_triggers(session)
        await create_system_profiles(session)

    log.info('Success!')
    log.info('Sequences have been reset to start at 1.')

    return 0


async def drop_and_create_tables(session):
    # for table_name in db.base.Base.metadata.tables.values():
    #     await session.execute(sqlalchemy.text(f'drop table if exists "{table_name.name}" cascade'))
    await session.run_sync(
        lambda sync_session: db.base.Base.metadata.drop_all(bind=sync_session.bind)
    )
    await session.run_sync(
        lambda sync_session: db.base.Base.metadata.create_all(bind=sync_session.bind)
    )


async def create_system_profiles(session):
    """Create the system profiles for public and authenticated users. This is a no-op for
    profiles that already exist.
    """
    udb = db.user.UserDb(session)
    for edi_id, common_name, init_avatar_func in (
        (
            Config.PUBLIC_EDI_ID,
            Config.PUBLIC_NAME,
            util.avatar.init_public_avatar,
        ),
        (
            Config.AUTHENTICATED_EDI_ID,
            Config.AUTHENTICATED_NAME,
            util.avatar.init_authenticated_avatar,
        ),
    ):
        if not (
            await session.execute(
                sqlalchemy.select(
                    sqlalchemy.exists().where(db.profile.Profile.edi_id == edi_id)
                )
            )
        ).scalar():
            await udb.create_profile(
                edi_id=edi_id,
                common_name=common_name,
                has_avatar=True,
            )
            init_avatar_func()


async def create_function_get_resource_tree(session):
    await session.execute(
        sqlalchemy.text(
            """
            do $$
            begin
                if not exists (select 1 from pg_proc where proname = 'get_resource_tree') then
                    create or replace function get_resource_tree(root_id integer)
                    returns table(id integer, label varchar, type varchar, parent_id integer)
                    language plpgsql
                    as $body$
                    begin
                        return query
                        with recursive resource_tree as (
                            select r.id, r.label, r.type, r.parent_id
                            from resource r
                            where r.id = root_id
                            union all
                            select r.id, r.label, r.type, r.parent_id
                            from resource r
                            inner join resource_tree rt on r.parent_id = rt.id
                        )
                        select * from resource_tree;
                    end;
                    $body$;
                end if;
            end;
            $$;
            """
        )
    )


async def create_function_get_resource_parents(session):
    await session.execute(
        sqlalchemy.text(
            """
            do $$
            begin
                if not exists (select 1 from pg_proc where proname = 'get_resource_parents') then
                    create or replace function get_resource_parents(node_id integer)
                    returns table(id integer, label varchar, type varchar, parent_id integer)
                    language plpgsql
                    as $body$
                    begin
                        return query
                        with recursive parent_tree as (
                            select r.id, r.label, r.type, r.parent_id
                            from resource r
                            where r.id = node_id
                            union all
                            select r.id, r.label, r.type, r.parent_id
                            from resource r
                            inner join parent_tree pt on r.id = pt.parent_id
                        )
                        select * from parent_tree;
                    end;
                    $body$;
                end if;
            end;
            $$;
            """
        )
    )


async def create_sync_triggers(session):
    """Create triggers to track table changes for synchronization with in-memory caches."""
    # Create trigger function. This function is called by the triggers to update the sync table.
    # A row for the given table name is created if it does not exist, or updated if it does.
    # In both cases, the updated timestamp is set to the current datetime.
    await session.execute(
        sqlalchemy.text(
            """
            do $$
            begin
                if not exists (select 1 from pg_proc where proname = 'sync_trigger_func') then
                    create or replace function sync_trigger_func()
                    returns trigger
                    language plpgsql
                    as $body$
                    begin
                        raise notice 'Sync trigger for table: %', TG_TABLE_NAME;
    
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
    )

    # Create triggers for each table
    for trigger_name, table_name in (
        ("sync_trigger_group", "\"group\""),
        ("sync_trigger_group_member", "group_member"),
        ("sync_trigger_identity", "identity"),
        ("sync_trigger_principal", "principal"),
        ("sync_trigger_profile", "profile"),
        ("sync_trigger_resource", "resource"),
        ("sync_trigger_rule", "rule"),
    ):
        await session.execute(
            sqlalchemy.text(
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
        )


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
