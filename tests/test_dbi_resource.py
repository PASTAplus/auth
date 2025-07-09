"""Tests for resource management in the database interface
"""

import re

import pytest
import sqlalchemy.exc
import tests.utils


pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(40),
]


async def test_create_db_instance(db):
    assert db is not None


async def test_get_new_edi_id(db):
    edi_id = db.get_new_edi_id()
    await _check_edi_id(edi_id)


async def test_list_profiles(client, populated_dbi):
    roger_edi_id = 'EDI-cfc6ddd2c43849559f0186331c44faac'
    token = await tests.utils.create_test_edi_token(roger_edi_id, populated_dbi)
    print(token)
    # profile_row = populated_dbi.get_profile(user_edi_id)
    # response = client.get('/v1/profile/list')
    # assert response.status_code == starlette.status.HTTP_200_OK
    # tests.sample.assert_equal_json(response.text, 'list_profiles.json')


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
