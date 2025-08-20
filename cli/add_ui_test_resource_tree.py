#!/usr/bin/env python

"""Replace database resources with a specifically structured test tree.

This scripts allows us to set up very specific test resources in the database, so that we can test
scenarios in the UI, without unrelated resources getting in the way.
"""
import argparse
import asyncio
import logging
import pathlib
import sys

import daiquiri
import sqlalchemy.exc

BASE_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((BASE_PATH / 'webapp').as_posix())

import db.db_interface
import db.models.group
import db.models.permission
import db.models.profile
import db.models.search
import db.session
import util.dependency
from config import Config


log = daiquiri.getLogger(__name__)


READ = db.models.permission.PermissionLevel.READ
WRITE = db.models.permission.PermissionLevel.WRITE
CHANGE = db.models.permission.PermissionLevel.CHANGE

PUBLIC = Config.PUBLIC_EDI_ID
ROGER = 'EDI-3afe2e74621f44718e7ed28019772160'
JOHN = 'EDI-11111111111111111111111111111111'

TEST_TREE = {
    ('pkg.1.2', 'package'): {
        'perm': (
            # (ROGER, READ),
            (ROGER, CHANGE),
            #     # (JOHN, WRITE),
            #     # (JOHN, CHANGE),
        ),
        # 'child': {
        #     ('r1', 'package'): {
        #         'perm': (
        #             # (PUBLIC, READ),
        #             # (ROGER, READ),
        #             # (JOHN, WRITE),
        #         )
        # }
    }
}


async def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--debug', help='Debug level logging')
    args = parser.parse_args()

    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

    async with util.dependency.get_session() as session:
        # Print database name
        log.info(f'Using database: {session.bind.url.database}')
        dbi = db.db_interface.DbInterface(session)

        # answer_str = input('Add test objects to the PRODUCTION database? (y/n): ')
        # if answer_str.lower() != 'y':
        #     log.info('Cancelled')
        #     return 1

        # await dbi.dump_raw_query('select * from principal')
        # await dbi.dump_raw_query('select * from profile')

        try:
            await dbi.get_profile(JOHN)
        except sqlalchemy.exc.NoResultFound:
            log.info(f'Creating profile for {JOHN}')
            await dbi.create_profile('John', 'john@gmail.com', False, JOHN)

        await dbi.execute(sqlalchemy.delete(db.models.search.SearchResult))
        await dbi.execute(sqlalchemy.delete(db.models.search.SearchSession))
        await dbi.execute(sqlalchemy.delete(db.models.search.PackageScope))
        await dbi.execute(sqlalchemy.delete(db.models.search.ResourceType))
        await dbi.execute(sqlalchemy.delete(db.models.search.RootResource))
        await dbi.execute(sqlalchemy.delete(db.models.permission.Rule))
        await dbi.execute(sqlalchemy.delete(db.models.permission.Resource))
        await dbi.flush()

        await _build_test_tree(dbi, TEST_TREE)

    log.info('Success!')

    return 0


async def _build_test_tree(dbi, tree_dict):
    """Build a tree of resources from the given recursive structure."""

    async def _build(d, parent_id=None, indent=0):
        for (key, type_str), sub_child_dict in d.items():
            # try:
            #     resource_row = await dbi.get_resource(key)
            # except sqlalchemy.exc.NoResultFound:
            resource_row = await dbi.create_resource(parent_id, key, key, type_str)

            if 'perm' in sub_child_dict:
                for edi_id, perm_level in sub_child_dict['perm']:
                    log.info(
                        f'{" " * indent}Adding permission for {edi_id} on {key} at level {perm_level}'
                    )
                    principal_row = await dbi.get_principal_by_edi_id(edi_id)
                    await dbi.create_or_update_rule(resource_row, principal_row, perm_level)
            if 'child' in sub_child_dict:
                await _build(sub_child_dict['child'], resource_row.id, indent + 4)

    await _build(tree_dict, None)


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
