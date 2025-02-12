#!/usr/bin/env python

"""Drop all tables in the database.
"""

import logging
import pathlib
import sys

import sqlalchemy.exc

ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((ROOT_PATH / 'webapp').as_posix())

import db.base
import db.iface

log = logging.getLogger(__name__)


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
        sequence_name = f"{table_name.name}_id_seq"
        session.execute(f"alter sequence {sequence_name} restart with 1")

    session.commit()

    db.base.Base.metadata.drop_all(db.iface.engine)


if __name__ == '__main__':
    sys.exit(main())
