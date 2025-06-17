"""Test the profile management APIs"""
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
import fastapi.testclient


# @pytest.mark.skip
@pytest.mark.asyncio
async def test_create(client: fastapi.testclient.TestClient):
    """createProfile() - Missing token -> 401 Unauthorized."""
    response = client.post('/auth/v1/profile')
    assert response.status_code == starlette.status.HTTP_401_UNAUTHORIZED


    # sample.assert_equal_json(response.text, 'list_profiles.json')


# @pytest.mark.asyncio
# async def test_get_profile(dbi, client: fastapi.testclient.TestClient, token):
#     """Test getting a profile by EDI ID."""
#     client.cookies.set_cookie('pasta_token', token)
#     token.cookies.set_cookie_header()
#     user_edi_id = 'EDI-d60512a1640247eb8030769008340e2b'
#     # response = await client.get(f'/v1/profile/{user_edi_id}', headers={'Authorization': f'Bearer {token}'})
#     # assert response.status_code == starlette.status.HTTP_200_OK
#     # profile_data = response.json()
#     # assert profile_data['edi_id'] == user_edi_id
#     # # Additional checks can be added here based on expected profile structure

# @pytest.mark.asyncio
# async def test_filter_query(dbi):
#     profile_row = await dbi.get_profile('EDI-d60512a1640247eb8030769008340e2b')
#     # query = await dbi.get_principal_id_query(profile_row)
#     # result = await dbi.session.execute(query)
#     # rows = result.scalars().all()
#     # print(rows)
#     edi_id_list = await dbi.get_equivalent_principal_edi_id_set(profile_row)
#     print(edi_id_list)
#
#     # execute query and print results
#     # pprint.pp([row.as_dict() for row in rows])
#
#     # print(token)
#     # profile_row = pop_dbi.get_profile(user_edi_id)
#     # response = client.get('/v1/profile/list')
#     # assert response.status_code == starlette.status.HTTP_200_OK
#     # sample.assert_equal_json(response.text, 'list_profiles.json')
