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
    existing_resource_key_set = set(await populated_dbi.get_all_resource_keys())
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
    existing_resource_key_set = set(await populated_dbi.get_all_resource_keys())
    assert 'a-new-resource-key' in existing_resource_key_set


@pytest.mark.asyncio
async def test_read_top_level_resource_with_valid_token(populated_dbi, john_client):
    """readResource()
    Successful call on top level resource -> The resource with the given resource_key, parent is
    None.
    """
    # "key": "623e07e2ab7c400eab9b572e9abc3733",
    # "label": "edi.7842.1",

    # profile:
    #       "edi_id": "EDI-147dd745c653451d9ef588aeb1d6a188",
    #       "email": "john@smith.com",
    #       "email_notifications": false,
    #       "common_name": "John Smith",
    #       "has_avatar": false,
    #       "id": 4,
    #       "privacy_policy_accepted": false,
    #       "privacy_policy_accepted_date": null

    # principal:
    #       "id": 5,
    #       "subject_id": 4,
    #       "subject_type": "PROFILE"
    #
    # rule:
    #       "id": 72,
    #       "permission": "READ",
    #       "principal_id": 5,
    #       "resource_id": 62
    #
    #       "id": 482,
    #       "permission": "CHANGE",
    #       "principal_id": 5,
    #       "resource_id": 341
    #
    # resource:
    #         "id": 341,
    #         "key": "2b22d840a07643d897588820343f8ac3",
    #         "label": "edi.8233.4",
    #         "parent_id": null,
    #         "type": "package"

    response = john_client.get('/v1/resource/2b22d840a07643d897588820343f8ac3')
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_equal_json(response.json(), 'read_top_level_resource_with_valid_token.json')


@pytest.mark.asyncio
async def test_read_child_resource_with_valid_token(john_client):
    """readResource()
    Successful call on child resource -> The resource with the given resource_key, with correct
    EDI-ID for the parent.
    """
    response = john_client.get('/v1/resource/9aad4c65801f4feb9373e7b3281955cf')
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_equal_json(response.json(), 'read_child_resource_with_valid_token.json')


@pytest.mark.asyncio
async def test_read_resource_by_non_owner(populated_dbi, john_client, jane_client):
    """readResource()
    Call by non-owner (no changePermission ACR on resource) -> 403 Forbidden
    """
    # John creates a resource, and becomes the owner
    john_client.post(
        '/v1/resource',
        json={
            'resource_key': 'john_resource_key',
            'resource_label': 'Resource created by John Smith',
            'resource_type': 'testResource',
            'parent_resource_key': None,
        },
    )
    # Jane tries to access John's resource without having any ACRs on the resource
    response = jane_client.get('/v1/resource/john_resource_key')
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_read_resource_tree_1(john_client):
    """readResourceTree()
    Successful call on resource at level-2 in the tree
    -> Full tree of resources that includes the given resource.
    """
    # Get a level-2 child resource (quality_report.xml, metadata)
    response = john_client.get('/v1/resource/2b22d840a07643d897588820343f8ac3')
    response = john_client.get('/v1/resource/tree/2b22d840a07643d897588820343f8ac3')
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_equal_json(response.json(), 'read_resource_tree_1.json')
