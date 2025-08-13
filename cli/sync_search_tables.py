#!/usr/bin/env python

"""Sync the search tables with the resource table.

The search tables are used to optimize searches for resources, packages, and scopes.

This synchronizes the search tables from the existing resources in the database, after which the
search tables are kept in sync by triggers on the resource table.

This command is useful in the following cases:

- If some error occurs that causes the search tables to drop out of sync with the resource table,
this command can be called to reset the search tables and repopulate them.

- If a resource is deleted, and the resource is the last resource of a given package scope or
resource type, the scope and type will remain in the search tables until this function is called.
The superfluous scopes and types won't break anything, but if they're selected in a search, they
won't return any results. The basic issue is that a simple implementation counting occurrences of a
specific label pattern (for package) in the resource table, when there are millions of rows, would
be too slow to do each time a resource is deleted. There are ways to implement this, but they add
complexity we don't need right now. Possible solutions to look into would be: (1) run this script as
a daily cron job, (2) maintaining a separate table with instance counts, (3) Use Postgres functional
indexes, (4) add columns to the resource table with calculated values, and have indexes on those.
"""

import asyncio
import logging
import pathlib
import sys

import daiquiri
import sqlalchemy

BASE_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((BASE_PATH / 'webapp').as_posix())

import util.dependency
import db.models.search

log = daiquiri.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    async with util.dependency.get_dbi() as dbi:
        await dbi.execute(sqlalchemy.delete(db.models.search.PackageScope))
        await dbi.execute(sqlalchemy.delete(db.models.search.ResourceType))
        await dbi.execute(sqlalchemy.delete(db.models.search.RootResource))
        await dbi.flush()
        # Force triggers to run on each existing resource row.
        await dbi.execute(sqlalchemy.text('update resource set id = id'))

    log.info('Success!')

    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
