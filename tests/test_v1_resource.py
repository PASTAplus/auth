"""Test the resource management APIs"""
import logging
import pytest
import starlette.status

import tests.sample
import tests.edi_id
import tests.utils


log = logging.getLogger(__name__)


#
# createResource()
#


@pytest.mark.asyncio
async def test_create_resource_anon(anon_client):
    """createResource()
    Missing token -> 401 Unauthorized.
    """
    response = anon_client.post('/v1/resource')
    assert response.status_code == starlette.status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_create_resource_with_valid_token(populated_dbi, john_client):
    """createResource()
    Successful call -> A new resource with a new resource_key.
    """
    existing_resource_key_set = {k for k in await populated_dbi.get_all_resource_keys()}
    assert 'a-new-resource-key' not in existing_resource_key_set
    response = john_client.post(
        '/v1/resource',
        json={
            'resource_key': 'a-new-resource-key',
            'resource_label': 'A new resource',
            'resource_type': 'testResource',
            'parent_resource_key': None,
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    existing_resource_key_set = {k for k in await populated_dbi.get_all_resource_keys()}
    assert 'a-new-resource-key' in existing_resource_key_set


@pytest.mark.asyncio
async def test_read_resource_with_valid_token(populated_dbi, john_client):
    """readResource()
    Successful call -> Returns the resource with the given resource_key.
    """
    # Create a resource
    response = john_client.post(
        '/v1/resource',
        json={
            'resource_key': 'john_resource_key',
            'resource_label': 'Resource created by John Smith',
            'resource_type': 'testResource',
            'parent_resource_key': None,
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    # # Read the resource
    response = john_client.get('/v1/resource/john_resource_key')
    assert response.status_code == starlette.status.HTTP_200_OK
    response_dict = response.json()
    tests.sample.assert_equal_json(response_dict, 'test_read_resource_with_valid_token.json')


@pytest.mark.asyncio
async def test_read_resource_include_parents(populated_dbi, john_client):
    """readResource()
    Successful call -> Returns the resource with the given resource_key.
    """
    # Create a resource
    response = john_client.post(
        '/v1/resource',
        json={
            'resource_key': 'john_resource_key',
            'resource_label': 'Resource created by John Smith',
            'resource_type': 'testResource',
            'parent_resource_key': None,
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    # # Read the resource
    response = john_client.get('/v1/resource/john_resource_key')
    assert response.status_code == starlette.status.HTTP_200_OK
    response_dict = response.json()
    tests.sample.assert_equal_json(response_dict, 'test_read_resource_with_valid_token.json')



# # # John creates a resource, and becomes the owner
# john_client.post(
#     '/v1/resource',
#     json={
#         'resource_key': 'john_resource_key',
#         'resource_label': 'Resource created by John Smith',
#         'resource_type': 'testResource',
#         'parent_resource_key': None,
#     }
# )
#
# # Jane tries to access John's resource without permission
# response = jane_client.get('/v1/resource/john_resource_key')
# assert response.status_code == starlette.status.HTTP_403_FORBIDDEN

# pass

# Simulate a token with insufficient permissions
# client.cookies.set_cookie('pasta_token', token)
# response = client.get('/v1/protected-resource')  # Replace with the actual endpoint
# assert response.status_code == starlette.status.HTTP_403_FORBIDDEN
# print(public_access_token)

# tests.sample.assert_equal_json(response.text, 'list_profiles.json')
