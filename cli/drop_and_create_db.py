#!/usr/bin/env python

"""Drop then create all the persistent objects in the database, such as tables, functions, and
triggers.
"""

import asyncio
import logging
import pathlib
import sys

import daiquiri

BASE_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((BASE_PATH / 'webapp').as_posix())

import db.models.base
import db.models.group
import db.session
import db.models.profile
import db.db_interface
import util.avatar
import util.dependency
import db.system_object

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

    async with util.dependency.get_dbi() as dbi:
        await db.system_object.init_system_objects(dbi)

    log.info('Success!')

    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
