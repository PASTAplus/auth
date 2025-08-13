"""Tests for v1 resource management APIs
"""
import logging
import pytest
import starlette.status

import tests.sample
import tests.edi_id
import tests.utils


log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(100),
]

#
# createResource()
#


async def test_create_resource_anon(anon_client):
    """createResource()
    Missing token -> 401 Unauthorized.
    """
    response = anon_client.post('/v1/resource')
    assert response.status_code == starlette.status.HTTP_401_UNAUTHORIZED


async def test_create_resource_with_valid_token(
    populated_dbi, john_client, service_profile_row, john_profile_row
):
    """createResource()
    Successful call -> A new resource with a new resource_key.
    """
    existing_resource_key_set = set(await populated_dbi.get_all_resource_keys())
    assert 'a-new-resource-key' not in existing_resource_key_set
    await tests.utils.add_vetted(populated_dbi, service_profile_row, john_profile_row)
    response = john_client.post(
        '/v1/resource',
        json={
            'resource_key': 'a-new-resource-key',
            'resource_label': 'A new resource',
            'resource_type': 'testResource',
            'parent_resource_key': None,
        },
    )
    # tests.utils.dump_response(response)
    assert response.status_code == starlette.status.HTTP_200_OK
    existing_resource_key_set = set(await populated_dbi.get_all_resource_keys())
    assert 'a-new-resource-key' in existing_resource_key_set


async def test_read_top_level_resource_with_valid_token(populated_dbi, john_client):
    """readResource()
    Successful call on top level resource -> The resource with the given resource_key, parent is
    None.
    """
    response = john_client.get('/v1/resource/2b22d840a07643d897588820343f8ac3')
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_match(response.json(), 'read_top_level_resource_with_valid_token.json')


# Needs ACR to be added
@pytest.mark.skip
async def test_read_child_resource_with_valid_token(john_client):
    """readResource()
    Successful call on child resource -> The resource with the given resource_key, with correct
    EDI-ID for the parent.
    """
    response = john_client.get('/v1/resource/9aad4c65801f4feb9373e7b3281955cf')
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_match(response.json(), 'read_child_resource_with_valid_token.json')


async def test_read_resource_by_non_owner(
    populated_dbi, john_client, jane_client, service_profile_row, john_profile_row
):
    """readResource()
    Call by non-owner (no changePermission ACR on resource) -> 403 Forbidden
    """
    # John creates a resource, and becomes the owner
    await tests.utils.add_vetted(populated_dbi, service_profile_row, john_profile_row)
    john_client.post(
        '/v1/resource',
        json={
            'resource_key': 'john-resource-key',
            'resource_label': 'Resource created by John Smith',
            'resource_type': 'testResource',
            'parent_resource_key': None,
        },
    )
    # Jane tries to read John's resource without having any ACRs on the resource
    response = jane_client.get('/v1/resource/john-resource-key')
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN


async def test_read_resource_tree_1(john_client):
    """readResourceTree()
    Successful call on resource at level-2 in the tree
    -> Full tree of resources that includes the given resource.
    """
    # Get a level-2 child resource (quality_report.xml, metadata)
    response = john_client.get('/v1/resource-tree/2b22d840a07643d897588820343f8ac3')
    tests.utils.dump_response(response)
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_match(response.json(), 'read_resource_tree_1.json')


# updateResource()


async def test_update_resource_by_anon(anon_client, john_client, populated_dbi, service_profile_row, john_profile_row):
    """updateResource()
    Call by anon user -> 401 Unauthorized
    """
    await _mk_resource(john_client, 'john-resource-key', populated_dbi, service_profile_row, john_profile_row)
    response = anon_client.put(
        f'/v1/resource/john-resource-key',
        json={
            'resource_label': 'Updated Resource Label',
        },
    )
    assert response.status_code == starlette.status.HTTP_401_UNAUTHORIZED


async def test_update_resource_by_non_writer(john_client, jane_client, populated_dbi, service_profile_row, john_profile_row):
    """updateResource()
    Call without WRITE on resource -> 403 Forbidden
    """
    await _mk_resource(john_client, 'john-resource-key', populated_dbi, service_profile_row, john_profile_row)
    # Jane tries to update John's resource without having any ACRs on the resource
    response = jane_client.put(
        f'/v1/resource/john-resource-key',
        json={
            'resource_label': 'Updated Resource Label',
        },
    )
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN


async def test_update_resource_by_writer(john_client, jane_client, populated_dbi, service_profile_row, john_profile_row):
    """updateResource()
    Call with WRITE on resource -> Successful update, 200 OK.
    """
    await _mk_resource(john_client, 'john-resource-key', populated_dbi, service_profile_row, john_profile_row)
    john_client.post(
        '/v1/rule',
        json={
            'resource_key': 'john-resource-key',
            'principal': tests.edi_id.JANE,
            'permission': 'write',
        },
    )
    # Jane updates John's resource with WRITE permission
    response = jane_client.put(
        f'/v1/resource/john-resource-key',
        json={
            'resource_label': 'Updated Resource Label',
            'resource_type': 'Update Resource Type',
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    # John can see the changes made by Jane
    response = john_client.get('/v1/resource/john-resource-key')
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_match(response.json(), 'update_resource_by_writer.json')


async def test_update_resource_valid_parent(john_client, jane_client, populated_dbi, service_profile_row, john_profile_row):
    """updateResource()
    Move resource from one parent to another -> Successful update, 200 OK.
    """
    # John creates two roots, and a child resource on one of the roots
    await _mk_resource(john_client, 'john-root-1', populated_dbi, service_profile_row, john_profile_row, parent_key=None)
    await _mk_resource(john_client, 'john-root-2', populated_dbi, service_profile_row, john_profile_row, parent_key=None)
    await _mk_resource(john_client, 'john-child-1', populated_dbi, service_profile_row, john_profile_row, parent_key='john-root-1')
    # John moves the child resource to the other root
    response = john_client.put(
        '/v1/resource/john-child-1',
        json={
            'resource_label': 'Updated Child Resource Label 2',
            'parent_resource_key': 'john-root-2',
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    response = john_client.get('/v1/resource/john-child-1')
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_match(response.json(), 'update_resource_valid_parent.json')


async def test_update_resource_invalid_parent(john_client, jane_client, populated_dbi, service_profile_row, john_profile_row):
    """updateResource()
    Move to parent without WRITE -> 403 Forbidden.
    """
    await _mk_resource(john_client, 'john-root', populated_dbi, service_profile_row, john_profile_row, parent_key=None)
    await _mk_resource(john_client, 'john-child', populated_dbi, service_profile_row, john_profile_row, parent_key='john-root')
    await _mk_resource(jane_client, 'jane-root', populated_dbi, service_profile_row, john_profile_row, parent_key=None)
    await _mk_resource(jane_client, 'jane-child', populated_dbi, service_profile_row, john_profile_row, parent_key='jane-root')
    # John tries to move the child resource to Jane's root, where he has no WRITE permission
    response = john_client.put(
        '/v1/resource/john-child',
        json={
            'resource_label': 'Updated Child Resource Label 2',
            'parent_resource_key': 'jane-root',
        },
    )
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN
    # John adds READ permission for Jane on his child resource
    response = john_client.post(
        '/v1/rule',
        json={
            'resource_key': 'john-child',
            'principal': tests.edi_id.JANE,
            'permission': 'read',
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    # Jane still cannot move John's child resource to her root, as she has no WRITE permission
    response = jane_client.put(
        '/v1/resource/john-child',
        json={
            'resource_label': 'Updated Child Resource Label 3',
            'parent_resource_key': 'jane-root',
        },
    )
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN
    # John updates Jane's permission to WRITE
    response = john_client.put(
        f'/v1/rule/{tests.edi_id.JANE}/john-child',
        json={
            'permission': 'write',
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    # Jane can now move John's child resource to her root
    response = jane_client.put(
        '/v1/resource/john-child',
        json={
            'resource_label': 'Updated Child Resource Label 4',
            'parent_resource_key': 'jane-root',
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    # Jane can see the changes made by herself
    response = jane_client.get('/v1/resource/john-child')
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_match(response.json(), 'update_resource_invalid_parent_jane.json')
    # John can see the changes made by Jane
    response = john_client.get('/v1/resource/john-child')
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_match(response.json(), 'update_resource_invalid_parent_john.json')


async def _mk_resource(client, key, populated_dbi, service_profile_row, john_profile_row, parent_key=None):
    await tests.utils.add_vetted(populated_dbi, service_profile_row, john_profile_row)
    return client.post(
        '/v1/resource',
        json={
            'resource_key': key,
            'resource_label': f'Resource label for {key}',
            'resource_type': f'Resource type for {key}',
            'parent_resource_key': parent_key,
        },
    )
