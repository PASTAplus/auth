#!/usr/bin/env python

"""Fill Profile table with random data.
"""

import logging
import pathlib
import sqlite3
import sys
import uuid

print(sys.path)
sys.path.append('.')
sys.path.append('./webapp')

import webapp.db.iface

log = logging.getLogger(__name__)


DB_PATH = pathlib.Path('~/git/auth/db.sqlite').expanduser().resolve()


def main():
    fill_profile()


def fill_profile():
    """Fill the Profile table with random data."""

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for s in RANDOM_PERSON_NAME_LIST:
            urid=f'PASTA-{uuid.uuid4().hex}'
            given_name, family_name = s.split(' ')
            email = f'{given_name.lower()}@{family_name.lower()}.com'
            cursor.execute('''
                insert into profile (urid, given_name, family_name, email, email_notifications, privacy_policy_accepted, has_avatar)
                values (?, ?, ?, ?, ?, ?, ?)
                ''',
                (urid, given_name, family_name, email, False, False, False),
            )
            # results = cursor.fetchall()
            # for row in results:
            #     print(row)
        conn.commit()
    except sqlite3.Error as e:
        print(f'Error: {e}')
    finally:
        if conn:
            conn.close()


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
    'Margaret King',
    'Anthony Wright',
    'Sandra Scott',
    'Mark Green',
    'Ashley Adams',
    'Donald Baker',
    'Kimberly Nelson',
    'Steven Carter',
    'Patricia Mitchell',
    'Paul Perez',
    'Carol Roberts',
    'Andrew Turner',
    'Michelle Phillips',
    'Joshua Campbell',
    'Amanda Parker',
    'Kenneth Evans',
    'Melissa Edwards',
    'Kevin Collins',
    'Stephanie Stewart',
    'Brian Sanchez',
    'Rebecca Morris',
    'George Rogers',
    'Laura Reed',
    'Edward Cook',
    'Sharon Morgan',
    'Ronald Bell',
    'Cynthia Murphy',
    'Timothy Bailey',
    'Angela Rivera',
    'Jason Cooper',
    'Brenda Richardson',
    'Jeffrey Cox',
    'Amy Howard',
    'Ryan Ward',
    'Anna Torres',
    'Jacob Peterson',
    'Kathleen Gray',
    'Gary Ramirez',
    'Shirley James',
    'Nicholas Watson',
    'Dorothy Brooks',
    'Eric Kelly',
    'Debra Sanders',
    'Stephen Price',
    'Frances Bennett',
    'Jonathan Wood',
    'Gloria Barnes',
    'Larry Ross',
    'Janet Henderson',
    'Justin Coleman',
    'Maria Jenkins',
    'Scott Perry',
    'Heather Powell',
    'Brandon Long',
    'Diane Patterson',
    'Benjamin Hughes',
    'Ruth Flores',
    'Samuel Washington',
    'Jacqueline Butler',
    'Gregory Simmons',
    'Kathy Foster',
    'Frank Gonzales',
    'Pamela Bryant',
    'Patrick Alexander',
    'Katherine Russell',
    'Raymond Griffin',
    'Christine Diaz',
    'Jack Hayes',
    'Ann Myers',
    'Dennis Ford',
    'Alice Hamilton',
    'Jerry Graham',
    'Julie Sullivan',
    'Tyler Wallace',
    'Megan West',
]


if __name__ == '__main__':
    sys.exit(main())
