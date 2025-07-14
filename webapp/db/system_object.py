"""Create system objects in the database, such as triggers and functions. Also creates the system
profiles and groups for the Service, Public and Authenticated users.
"""

import sqlalchemy
import util.avatar

import db.models.base

from config import Config


async def init_system_objects(dbi):
    await _drop_and_create_tables(dbi)
    await _create_function_get_resource_descendants(dbi)
    await _create_function_get_resource_ancestors(dbi)
    await _create_sync_triggers(dbi)
    await _create_system_profiles(dbi)
    await _create_system_groups(dbi)


async def _drop_and_create_tables(dbi):
    # for table_name in db.models.base.Base.metadata.tables.values():
    #     await dbi.execute(sqlalchemy.text(f'drop table if exists "{table_name.name}" cascade'))
    await dbi.session.run_sync(
        lambda sync_session: db.models.base.Base.metadata.drop_all(bind=sync_session.bind)
    )
    await dbi.session.run_sync(
        lambda sync_session: db.models.base.Base.metadata.create_all(bind=sync_session.bind)
    )


async def _create_system_profiles(dbi):
    """Create the system profiles for the Public and Authenticated users. This is a no-op for
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
    """Create the system groups for the Public and Authenticated users. This is a no-op for
    groups that already exist.
    """
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
                raise notice 'Sync trigger for table: %', TG_TABLE_NAME;

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
        await dbi.execute(
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
