#!/usr/bin/env python

import logging
import pathlib
import sys

import daiquiri
import sqlalchemy.exc

ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((ROOT_PATH / 'webapp').as_posix())

import db.profile
import db.iface
import db.permission
import db.group

log = daiquiri.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    session = db.iface.SessionLocal()

    try:
        session.query(db.permission.Rule).filter(
            db.permission.Rule.resource_id.in_(
                session.query(db.permission.Resource.id).filter(
                    db.permission.Resource.label == 'group'
                )
            )
        ).delete()

        session.query(db.permission.Resource).filter(
            db.permission.Resource.label == 'group'
        ).delete()

        session.query(db.permission.Collection).filter(
            db.permission.Collection.type == 'group'
        ).delete()

        add_permissions(session)
    except sqlalchemy.exc.SQLAlchemyError as e:
        log.error(f'Error: {e}')
        session.rollback()
        return 1

    session.commit()

    log.info('Collections, resources and permissions have been added')

    return 0


def add_permissions(session):
    for g in session.query(db.group.Group):
        new_collection = db.permission.Collection(
            label=g.name,
            type='group',
        )
        session.add(new_collection)
        session.flush()

        new_resource = db.permission.Resource(
            collection_id=new_collection.id,
            label='group',
            type=f'Owner: {g.profile.full_name}',
        )
        session.add(new_resource)
        session.flush()

        # new_permission = db.permission.Rule(
        #     resource_id=new_resource.id,
        #     principal_id=profile_id,
        #     principal_type=db.permission.EntityType.PROFILE,
        #     level=level,
        # )
        # session.add(new_permission)
        # session.flush()

    session.commit()


if __name__ == '__main__':
    sys.exit(main())
