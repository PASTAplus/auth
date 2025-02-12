#!/usr/bin/env python

"""Fill profile table with random data.
"""

import logging
import pathlib
import sys
import uuid

import sqlalchemy.exc

ROOT_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((ROOT_PATH / 'webapp').as_posix())

import db.profile
import db.iface

log = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    session = db.iface.SessionLocal()

    try:
        fill_profile(session)
    except sqlalchemy.exc.SQLAlchemyError as e:
        log.error(f'Error: {e}')
        session.rollback()
        return 1

    session.commit()

    log.info('Profiles have been added')

    return 0


def fill_profile(session):
    for s in RANDOM_PERSON_NAME_LIST:
        pasta_id = f'PASTA-{uuid.uuid4().hex}'
        given_name, family_name = s.split(' ')
        email = f'{given_name.lower()}@{family_name.lower()}.com'
        new_profile = db.profile.Profile(
            pasta_id=pasta_id,
            given_name=given_name,
            family_name=family_name,
            email=email,
        )
        session.add(new_profile)


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
    sys.exit(main())
