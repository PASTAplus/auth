#!/usr/bin/env python

"""Fill the group and group member tables with random data.
"""
import asyncio
import logging
import pathlib
import random
import sys
import uuid

import daiquiri
import sqlalchemy.exc

ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((ROOT_PATH / 'webapp').as_posix())

import db.profile
import db.iface
import db.group
import db.user

log = daiquiri.getLogger(__name__)
udb: db.user.UserDb = db.iface.get_udb()
session = udb.session

async def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    # session = db.iface.SessionLocal()

    try:
        # session.query(db.group.GroupMember).delete()
        # session.query(db.group.Group).delete()
        # session.commit()
        await add_groups()
        pass
    except sqlalchemy.exc.SQLAlchemyError as e:
        log.error(f'Error: {e}')
        session.rollback()
        return 1

    # session.commit()

    log.info('Groups and group members have been added')

    return 0


async def add_groups():
    profile_id_list = await get_profile_rows()
    for profile_row in profile_id_list:
        await insert_groups(profile_row, profile_id_list)


async def insert_groups(profile_row, profile_id_list):
    group_count = random.randrange(0, 5)
    for group_idx in range(group_count):
        group_name = f'{profile_row.given_name}\'s group #{group_idx}'
        group_row = await udb.create_group(profile_row, group_name, None)
        # new_group = db.group.Group(profile_id=profile_row, edi_id=edi_id, name=group_name)
        # session.add(new_group)
        # session.flush()
        # group_id = new_group.id
        await insert_members(group_row, profile_id_list)


async def insert_members(group_row, profile_id_list):
    member_count = random.randrange(1, 5)
    sampled_profile_id_list = random.sample(profile_id_list, member_count)
    for member_profile_id, _member_given_name in sampled_profile_id_list:
        new_group_member = db.group.GroupMember(
            group=group_row,
            profile_id=member_profile_id,
        )
        session.add(new_group_member)


async def get_profile_rows():
    return session.query(db.profile.Profile).all()
    # return [(r.id, r.given_name) for r in row_list]


if __name__ == '__main__':
    asyncio.run(main())
