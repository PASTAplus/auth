import json
import pprint

import pytest
import sqlalchemy
import starlette.status

import db.models.profile
import sample
import tests.utils
import db.resource_tree
import db.models.permission


@pytest.mark.skip
@pytest.mark.asyncio
async def test_ping(client):
    response = client.get('/auth/v1/ping')
    assert response.status_code == starlette.status.HTTP_200_OK
    assert response.text == 'pong'


@pytest.mark.skip
@pytest.mark.asyncio
async def test_pop_session(pop_session):
    s = pop_session
    edi_id_list = [
        p.edi_id
        for p in (await s.execute(sqlalchemy.select(db.models.profile.Profile))).scalars().all()
    ]
    assert len(edi_id_list) > 10


@pytest.mark.skip
@pytest.mark.asyncio
async def test_list_profiles(client, pop_dbi):
    roger_edi_id = 'EDI-cfc6ddd2c43849559f0186331c44faac'
    token = await tests.utils.create_test_pasta_token(roger_edi_id, pop_dbi)
    print(token)
    # profile_row = pop_dbi.get_profile(user_edi_id)
    # response = client.get('/v1/profile/list')
    # assert response.status_code == starlette.status.HTTP_200_OK
    # sample.assert_equal_json(response.text, 'list_profiles.json')


@pytest.mark.skip
@pytest.mark.asyncio
async def test_list_profiles2(client, pop_session):
    """Test the /v1/profile/list endpoint."""
    result = (await popexecute(sqlalchemy.select(db.models.profile.Profile))).scalars().all()
    print([p.edi_id for p in result])


@pytest.mark.skip
@pytest.mark.asyncio
async def test_3(client, pop_dbi, profile_row):
    #     rows = (await pop_dbi.session.execute(sqlalchemy.select(db.models.permission.Rule))).scalars().all()
    #     for row in rows:
    #         print('-' * 80)
    #         print(row)
    #         print(row.id)
    #         print(row.permission)
    resource_query = await pop_dbi.get_resource_parents(
        profile_row, (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    )
    resource_tree = db.resource_tree.get_resource_tree_for_ui(resource_query)
    # pprint.pp(resource_tree)
    print(json.dumps(resource_tree, indent=2))


# @pytest.mark.skip
@pytest.mark.asyncio
async def test_4(client, pop_dbi):
    resource_query = await pop_dbi.get_resource_list(profile_row, '', None)
    resource_tree = db.resource_tree.get_resource_tree_for_ui(resource_query)
    # pprint.pp(resource_tree)
    print(json.dumps(resource_tree, indent=2))


# # @pytest.mark.skip
# def test_map_identity(client, pop_dbi):
#     token_a = tests.util.create_test_pasta_token(
#         'EDI-e851e1a4b19c4b78992455807fe79534', pop_dbi
#     )
#     token_b = tests.util.create_test_pasta_token(
#         'EDI-61b8b8872c13469faf4a44e3ff50b848', pop_dbi
#     )
#     response = client.post(
#         '/v1/profile/map', params={'token_src_str': token_a, 'token_dst_str': token_b}
#     )
#     assert response.status_code == starlette.status.HTTP_200_OK
#     db_json = tests.util.get_db_as_json(pop_dbi)
#     sample.assert_equal_json(db_json, 'map_identity.json')
#
#
# def test_get_profile(client, pop_dbi):
#     token = tests.util.create_test_pasta_token(
#         'EDI-61b8b8872c13469faf4a44e3ff50b848', pop_dbi
#     )
#     response = client.get('/v1/profile/get', params={'token_str': token})
#     assert response.status_code == starlette.status.HTTP_200_OK
#     sample.assert_equal_json(response.text, 'get_profile.json')
#
#
# def test_profile_disable(client, pop_dbi):
#     token = tests.util.create_test_pasta_token(
#         'EDI-61b8b8872c13469faf4a44e3ff50b848', pop_dbi
#     )
#     response = client.post('/v1/profile/disable', params={'token_str': token})
#     assert response.status_code == starlette.status.HTTP_200_OK
#     db_json = tests.util.get_db_as_json(pop_dbi)
#     sample.assert_equal_json(db_json, 'profile_disable.json')
#
#
# def test_identity_drop(client, pop_dbi):
#     token = tests.util.create_test_pasta_token(
#         'EDI-c422bd31545b4d7080a84ef1ba4a6a67', pop_dbi
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
#     db_json = tests.util.get_db_as_json(pop_dbi)
#     sample.assert_equal_json(db_json, 'profile_drop.json')
#
#
# def test_identity_list(client, pop_dbi):
#     token = tests.util.create_test_pasta_token(
#         'EDI-61b8b8872c13469faf4a44e3ff50b848', pop_dbi
#     )
#     response = client.get('/v1/identity/list', params={'token_str': token})
#     assert response.status_code == starlette.status.HTTP_200_OK
#     sample.assert_equal_json(response.text, 'identity_list.json')
