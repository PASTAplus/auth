#!/usr/bin/env python

"""Drop all tables in the database.
"""

import logging
import pathlib
import sys

import daiquiri
import sqlalchemy.exc

ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((ROOT_PATH / 'webapp').as_posix())

import db.base
import db.iface

log = daiquiri.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    answer_str = input(
        'Are you sure you want to drop all tables and other objects in the database? '
        '(y/n): '
    )
    if answer_str.lower() != 'y':
        log.info('Cancelled')
        return 1

    session = db.iface.SessionLocal()

    try:
        clear_database(session)
    except sqlalchemy.exc.SQLAlchemyError as e:
        log.error(f'Error: {e}')
        session.rollback()
        return 1

    session.commit()

    log.info('All tables and other objects have been dropped.')
    log.info('Sequences have been reset to start at 1.')

    return 0


def clear_database(session):
    for table_name in db.base.Base.metadata.tables.values():
        session.execute(
            sqlalchemy.text(f'drop table if exists "{table_name.name}" cascade')
        )

    session.commit()

    db.base.Base.metadata.drop_all(db.iface.engine)


if __name__ == '__main__':
    sys.exit(main())
