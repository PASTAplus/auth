#!/usr/bin/env python

"""Fill profile table with random data.
"""
import asyncio
import logging
import pathlib
import sys
import uuid

import daiquiri

ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((ROOT_PATH / 'webapp').as_posix())

import util.dependency

log = daiquiri.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    async with util.dependency.get_udb() as udb:
        await fill_profile(udb)

    log.info('Profiles have been added')

    return 0


async def fill_profile(udb):
    for s in RANDOM_PERSON_NAME_LIST:
        edi_id = f'EDI-{uuid.uuid4().hex}'
        given_name, family_name = s.split(' ')
        email = f'{given_name.lower()}@{family_name.lower()}.com'
        await udb.create_profile(edi_id, given_name, family_name, email)


RANDOM_PERSON_NAME_LIST = [
    'John Smith',
    'Jane Doe',
    'Michael Johnson',
    'Emily Davis',
    'James Brown',
    'Mary Wilson',
    'Robert Taylor',
    'Linda Anderson',
    'William Thomas',
    'Barbara Jackson',
    'David White',
    'Susan Harris',
    'Richard Martin',
    'Jessica Thompson',
    'Charles Garcia',
    'Sarah Martinez',
    'Joseph Robinson',
    'Karen Clark',
    'Thomas Rodriguez',
    'Nancy Lewis',
    'Christopher Lee',
    'Lisa Walker',
    'Daniel Hall',
    'Betty Allen',
    'Matthew Young',
    # 'Margaret King',
    # 'Anthony Wright',
    # 'Sandra Scott',
    # 'Mark Green',
    # 'Ashley Adams',
    # 'Donald Baker',
    # 'Kimberly Nelson',
    # 'Steven Carter',
    # 'Patricia Mitchell',
    # 'Paul Perez',
    # 'Carol Roberts',
    # 'Andrew Turner',
    # 'Michelle Phillips',
    # 'Joshua Campbell',
    # 'Amanda Parker',
    # 'Kenneth Evans',
    # 'Melissa Edwards',
    # 'Kevin Collins',
    # 'Stephanie Stewart',
    # 'Brian Sanchez',
    # 'Rebecca Morris',
    # 'George Rogers',
    # 'Laura Reed',
    # 'Edward Cook',
    # 'Sharon Morgan',
    # 'Ronald Bell',
    # 'Cynthia Murphy',
    # 'Timothy Bailey',
    # 'Angela Rivera',
    # 'Jason Cooper',
    # 'Brenda Richardson',
    # 'Jeffrey Cox',
    # 'Amy Howard',
    # 'Ryan Ward',
    # 'Anna Torres',
    # 'Jacob Peterson',
    # 'Kathleen Gray',
    # 'Gary Ramirez',
    # 'Shirley James',
    # 'Nicholas Watson',
    # 'Dorothy Brooks',
    # 'Eric Kelly',
    # 'Debra Sanders',
    # 'Stephen Price',
    # 'Frances Bennett',
    # 'Jonathan Wood',
    # 'Gloria Barnes',
    # 'Larry Ross',
    # 'Janet Henderson',
    # 'Justin Coleman',
    # 'Maria Jenkins',
    # 'Scott Perry',
    # 'Heather Powell',
    # 'Brandon Long',
    # 'Diane Patterson',
    # 'Benjamin Hughes',
    # 'Ruth Flores',
    # 'Samuel Washington',
    # 'Jacqueline Butler',
    # 'Gregory Simmons',
    # 'Kathy Foster',
    # 'Frank Gonzales',
    # 'Pamela Bryant',
    # 'Patrick Alexander',
    # 'Katherine Russell',
    # 'Raymond Griffin',
    # 'Christine Diaz',
    # 'Jack Hayes',
    # 'Ann Myers',
    # 'Dennis Ford',
    # 'Alice Hamilton',
    # 'Jerry Graham',
    # 'Julie Sullivan',
    # 'Tyler Wallace',
    # 'Megan West',
]


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
