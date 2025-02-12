#!/usr/bin/env python

"""Fill the group and group member tables with random data.
"""
import logging
import pathlib
import random
import sys
import uuid

import sqlalchemy.exc

ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((ROOT_PATH / 'webapp').as_posix())

import db.profile
import db.iface
import db.group

log = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    session = db.iface.SessionLocal()

    try:
        session.query(db.group.GroupMember).delete()
        session.query(db.group.Group).delete()
        add_groups(session)
    except sqlalchemy.exc.SQLAlchemyError as e:
        log.error(f'Error: {e}')
        session.rollback()
        return 1

    session.commit()

    log.info('Groups and group members have been added')

    return 0

def add_groups(session):
    profile_id_list = get_profile_id_list(session)
    log.debug(f'profile_id_list: {profile_id_list}')

    for (profile_id, profile_given_name) in profile_id_list:
        insert_groups(session, profile_id, profile_given_name, profile_id_list)


def insert_groups(session, profile_id, profile_given_name, profile_id_list):
    group_count = random.randrange(0, 5)
    for group_idx in range(group_count):
        pasta_id = f'PASTA-{uuid.uuid4().hex}'
        group_name = f'{profile_given_name}\'s group #{group_idx}'
        new_group = db.group.Group(profile_id=profile_id, pasta_id=pasta_id, name=group_name)
        session.add(new_group)
        session.flush()
        group_id = new_group.id
        insert_members(session, profile_id_list, group_id)


def insert_members(session, profile_id_list, group_id):
    member_count = random.randrange(1, 5)
    sampled_profile_id_list = random.sample(profile_id_list, member_count)
    for member_profile_id, _member_given_name in sampled_profile_id_list:
        new_group_member = db.group.GroupMember(
            group_id=group_id,
            profile_id=member_profile_id,
        )
        session.add(new_group_member)


def get_profile_id_list(session):
    row_list = session.query(db.profile.Profile).all()
    return [(r.id, r.given_name) for r in row_list]


if __name__ == '__main__':
    sys.exit(main())
