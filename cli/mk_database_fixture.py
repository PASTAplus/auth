#!/usr/bin/env python

"""
Capture the current state of the database to a DB fixture.

To create the fixture, commands are typically run in this order:

./cli/drop_and_create_db.py
./cli/add_test_profiles.py
./cli/add_test_groups.py
./cli/add_test_resources.py
./cli/mk_database_fixture.py

Order of tables, with dependencies before their dependents:

profile
profile_history
identity
group
group_member
resource
principal
rule
sync

See conftest.py for the fixture that populates the database from the JSON file generated here.
"""
import asyncio
import datetime
import json
import logging
import pathlib
import sys

import sqlalchemy
import sqlalchemy.ext.asyncio

BASE_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((BASE_PATH / 'webapp').as_posix())

import db.models.permission
import db.models.base
import util.dependency

DB_FIXTURE_PATH = BASE_PATH / 'tests/test_files/db_fixture.json'

log = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.DEBUG)

    async with util.dependency.get_session() as async_session:
        await export_database_to_json(async_session, DB_FIXTURE_PATH)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, db.models.permission.SubjectType):
            return obj.name
        elif isinstance(obj, db.models.permission.PermissionLevel):
            return obj.name
        return super().default(obj)


async def export_database_to_json(
    session: sqlalchemy.ext.asyncio.AsyncSession,
    output_file: pathlib.Path,
):
    """Export entire database to JSON"""
    fixture_dict = {}
    for table_name, table in db.models.base.Base.metadata.tables.items():
        print(f'Exporting {table_name}...')
        result = await session.execute(sqlalchemy.select(table))
        rows = result.fetchall()
        fixture_dict[table_name] = [dict(row._mapping) for row in rows]

    output_file.write_text(
        json.dumps(fixture_dict, indent=4, sort_keys=True, cls=CustomJSONEncoder)
    )


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
