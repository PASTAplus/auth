#!/usr/bin/env python
import asyncio
import json
import pprint
import sys

import sqlalchemy

sys.path.append('webapp')

import db
import db.db_interface


DbInterface = db.db_interface.DbInterface

engine = sqlalchemy.create_engine(
    'sqlite:///auth.sqlite',
    echo=True,
    connect_args={
        'check_same_thread': False,
    },
)

AsyncSessionFactory = sqlalchemy.orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)


u = db.db_interface.DbInterface(AsyncSessionFactory())


async def main():
    res = await u.get_resource_list(None, '')

    print()
    print()
    pprint.pp(res, width=1)
    print()
    print()

    class SetEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, set):
                return sorted(list(obj))
            return super().default(obj)

    print(json.dumps(res, indent=2, cls=SetEncoder))

    # for coll in res:
    #     print(coll['label'])

    # r2 = get_client_aggregate_collection_list(res)
    # print()
    # print()
    # pprint.pp(r2, width=1)


def get_client_aggregate_collection_list(collection_list):
    """Create a set of JSON serializable key/value dicts with limited resource values for
    exposing client side.
    """
    ret = []

    for c in collection_list:
        # agg_resource_list = get_client_aggregate_resource_list(c['collection'].resources)
        #
        # for i, r in enumerate(agg_resource_list):
        #     for ppp in r['permission_list']:
        #         ppp['permission_level'] = permission_level_name(ppp['permission_level'])

        ret.append(
            {
                'collection_id': c.id,
                'collection_label': c.label,
                'collection_type': c.type_str,
                # 'collection_created_date': c['collection'].created_date.strftime(
                #     '%m/%d/%Y %I:%M %p'
                # ),
                'resource_list': get_client_aggregate_resource_list(c.resources),
            }
        )

    return ret


def get_client_aggregate_resource_list(resource_list):
    # agg_type = {}

    # for r in resource_list:
    #     agg_type.setdefault(r.type, {})
    #     agg_perm(agg_type[r.type], r.permissions)

    ret = []

    for r in resource_list:

        ret.append(
            {
                'id': r.id,
                'label': r.label,
                'type_title': r.type.title(),
                # 'type': k,
                # 'permission_list': list(v.values()),
            }
        )

    return ret


def agg_perm(agg, permission_list):
    for p in permission_list:
        if p.profile_id not in agg:
            agg[p.profile_id] = {
                'common_name': p.profile.common_name,
                'edi_id': p.profile.edi_id[:12] + '\u2026',
                'granted_date': p.granted_date.strftime('%m/%d/%Y %I:%M %p'),
                'permission_level': p.permission_level.value,
            }
        else:
            agg[p.profile_id]['permission_level'] = max(
                agg[p.profile_id]['permission_level'], p.permission_level.value
            )


def permission_level_name(permission_level):
    return {
        1: 'Reader',
        2: 'Editor',
        3: 'Owner',
    }[permission_level]


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
