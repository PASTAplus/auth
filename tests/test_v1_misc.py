"""Tests for miscellaneous v1 APIs
"""

import json
import pprint

import pytest
import sqlalchemy
import starlette.status

import db.models.profile
import tests.sample
import tests.utils
import db.resource_tree
import db.models.permission

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(100),
]

async def test_ping(anon_client):
    response = anon_client.get('/v1/ping')
    assert response.status_code == starlette.status.HTTP_200_OK
    assert response.text == 'pong'

# # @pytest.mark.skip
# def test_map_identity(client, populated_dbi):
#     token_a = tests.util.create_test_edi_token(
#         'EDI-e851e1a4b19c4b78992455807fe79534', populated_dbi
#     )
#     token_b = tests.util.create_test_edi_token(
#         'EDI-61b8b8872c13469faf4a44e3ff50b848', populated_dbi
#     )
#     response = client.post(
#         '/v1/profile/map', params={'token_src_str': token_a, 'token_dst_str': token_b}
#     )
#     assert response.status_code == starlette.status.HTTP_200_OK
#     db_json = tests.util.get_db_as_json(populated_dbi)
#     tests.sample.assert_match(db_json, 'map_identity.json')
#
#
# def test_get_profile(client, populated_dbi):
#     token = tests.util.create_test_edi_token(
#         'EDI-61b8b8872c13469faf4a44e3ff50b848', populated_dbi
#     )
#     response = client.get('/v1/profile/get', params={'token_str': token})
#     assert response.status_code == starlette.status.HTTP_200_OK
#     tests.sample.assert_match(response.text, 'get_profile.json')
#
#
# def test_profile_disable(client, populated_dbi):
#     token = tests.util.create_test_edi_token(
#         'EDI-61b8b8872c13469faf4a44e3ff50b848', populated_dbi
#     )
#     response = client.post('/v1/profile/disable', params={'token_str': token})
#     assert response.status_code == starlette.status.HTTP_200_OK
#     db_json = tests.util.get_db_as_json(populated_dbi)
#     tests.sample.assert_match(db_json, 'profile_disable.json')
#
#
# def test_identity_drop(client, populated_dbi):
#     token = tests.util.create_test_edi_token(
#         'EDI-c422bd31545b4d7080a84ef1ba4a6a67', populated_dbi
#     )
#     response = client.post(
#         '/v1/identity/drop',
#         params={
#             'token_str': token,
#             'idp_name': 'github',
#             'uid': 'https://github.com/testuser',
#         },
#     )
#     assert response.status_code == starlette.status.HTTP_200_OK
#     db_json = tests.util.get_db_as_json(populated_dbi)
#     tests.sample.assert_match(db_json, 'profile_drop.json')
#
#
# def test_identity_list(client, populated_dbi):
#     token = tests.util.create_test_edi_token(
#         'EDI-61b8b8872c13469faf4a44e3ff50b848', populated_dbi
#     )
#     response = client.get('/v1/identity/list', params={'token_str': token})
#     assert response.status_code == starlette.status.HTTP_200_OK
#     tests.sample.assert_match(response.text, 'identity_list.json')
