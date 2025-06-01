#!/usr/bin/env python

"""Fill the group and group member tables with random data.
"""
import asyncio
import logging
import pathlib
import random
import sys

import daiquiri
import sqlalchemy.exc

ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((ROOT_PATH / 'webapp').as_posix())

import db.profile
import db.group
import util.dependency
import db.permission

from config import Config

SYSTEM_EDI_ID_LIST = (
    Config.PUBLIC_EDI_ID,
    Config.AUTHENTICATED_EDI_ID,
)

log = daiquiri.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    async with util.dependency.get_udb() as udb:
        await add_groups(udb)

    log.info('Groups and group members have been added')

    return 0


async def add_groups(udb):
    profile_row_list = await get_profile_rows(udb)
    for profile_row in profile_row_list:
        await insert_groups(udb, profile_row, profile_row_list)


async def insert_groups(udb, profile_row, profile_row_list):
    group_count = random.randrange(0, 5)
    for group_idx in range(group_count):
        group_name = f'{profile_row.common_name}\'s group #{group_idx}'
        group_row = await udb.create_group(profile_row, group_name, None)
        await insert_members(udb, group_row, profile_row_list)
        await insert_permission(udb, group_row, profile_row)


async def insert_members(udb, group_row, profile_row_list):
    member_count = random.randrange(1, 5)
    sampled_profile_row_list = random.sample(profile_row_list, member_count)
    for profile_row in sampled_profile_row_list:
        new_group_member = db.group.GroupMember(
            group=group_row,
            profile=profile_row,
        )
        udb.session.add(new_group_member)


async def get_profile_rows(udb):
    return (
        (
            await udb.session.execute(
                sqlalchemy.select(db.profile.Profile).where(
                    ~db.profile.Profile.edi_id.in_(SYSTEM_EDI_ID_LIST)
                )
            )
        )
        .scalars()
        .all()
    )


async def insert_permission(udb, group_row, profile_row):
    """Insert a resource and rule for tracking permissions for a group."""
    new_resource_row = udb.create_resource(
        parent_id=None,
        key=group_row.edi_id,
        label='group',
        type=f'Owner: {profile_row.common_name}',
    )
    await udb.session.flush()

    principal_row = await udb.get_principal_by_profile(profile_row)

    udb._create_or_update_permission(
        new_resource_row,
        principal_row,
        db.permission.PermissionLevel.CHANGE,
    )


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
