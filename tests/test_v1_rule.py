"""Tests for v1 resource management APIs"""

import logging
import pytest
import starlette.status

import tests.sample
import tests.edi_id
import tests.utils

import edi_id

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(100),
]

#
# createResource()
#


async def test_create_rule_anon(anon_client):
    """createRule()
    Missing token -> 401 Unauthorized.
    """
    response = anon_client.post('/v1/rule')
    assert response.status_code == starlette.status.HTTP_401_UNAUTHORIZED


async def test_create_rule_by_non_owner(
    populated_dbi, john_client, jane_client, john_profile_row, service_profile_row
):
    """createResource()
    Call by non-owner (no changePermission ACR on resource) -> 403 Forbidden
    """
    # John creates a resource, and becomes the owner
    await tests.utils.add_vetted(populated_dbi, service_profile_row, john_profile_row)
    await populated_dbi.flush()
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
    await populated_dbi.flush()
    # Jane tries to create a rule on John's resource without having any ACRs on the resource
    response = jane_client.post(
        '/v1/rule',
        json={
            'resource_key': 'a-new-resource-key',
            'principal': edi_id.PUBLIC_ACCESS,
            'permission': 'read',
        },
    )
    tests.sample.assert_match(response.json(), 'create_rule_by_non_owner.json')
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN


async def test_create_rule_by_owner(
    populated_dbi, john_client, jane_client, service_profile_row, john_profile_row
):
    """createRule()
    Successful call by owner -> A new rule is created on the resource.
    """
    # John creates a resource, and receives implicit CHANGE
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
    assert response.status_code == starlette.status.HTTP_200_OK
    # # John can read the resource
    # response = john_client.get('/v1/resource/a-new-resource-key')
    # assert response.status_code == starlette.status.HTTP_200_OK
    # # Jane cannot read the resource
    # response = jane_client.get('/v1/resource/a-new-resource-key')
    # assert response.status_code == starlette.status.HTTP_403_FORBIDDEN
    # # John adds WRITE for Jane
    # response = john_client.post(
    #     '/v1/rule',
    #     json={
    #         'resource_key': 'a-new-resource-key',
    #         'principal': edi_id.JANE,
    #         'permission': 'read',
    #     }
    # )
    # assert response.status_code == starlette.status.HTTP_200_OK
    # # Jane can now read the resource
    # response = jane_client.get('/v1/resource/a-new-resource-key')
    # assert response.status_code == starlette.status.HTTP_200_OK
    # # Jane still cannot create a rule on the resource, as she has only WRITE, not CHANGE
    # response = jane_client.post(
    #     '/v1/rule',
    #     json={
    #         'resource_key': 'a-new-resource-key',
    #         'principal': edi_id.PUBLIC_ACCESS,
    #         'permission': 'read',
    #     }
    # )
    # assert response.status_code == starlette.status.HTTP_403_FORBIDDEN


async def test_public_access(
    populated_dbi, service_client, service_profile_row, john_client, jane_client
):
    """createRule()
    Adding the Public Access principal to a resource -> Everyone can read the resource.
    """
    # The Service principal creates a resource, and receives implicit CHANGE

    # Add Service to the Vetted system group.
    await tests.utils.add_vetted(populated_dbi, service_profile_row, service_profile_row)
    response = service_client.post(
        '/v1/resource',
        json={
            'resource_key': 'public-access-resource',
            'resource_label': 'Public Access Resource',
            'resource_type': 'testResource',
            'parent_resource_key': None,
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK

    # Neither John nor Jane can read the resource yet
    response = john_client.get('/v1/resource/public-access-resource')
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN
    response = jane_client.get('/v1/resource/public-access-resource')
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN
    # System adds Public Access rule
    response = service_client.post(
        '/v1/rule',
        json={
            'resource_key': 'public-access-resource',
            'principal': edi_id.PUBLIC_ACCESS,
            'permission': 'read',
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    # The service client can still read the resource
    response = service_client.get('/v1/resource/public-access-resource')
    assert response.status_code == starlette.status.HTTP_200_OK
    # Now both John and Jane can read the resource
    response = john_client.get('/v1/resource/public-access-resource')
    assert response.status_code == starlette.status.HTTP_200_OK
    response = jane_client.get('/v1/resource/public-access-resource')
    assert response.status_code == starlette.status.HTTP_200_OK
    # John and Jane do not have CHANGE
    response = john_client.post(
        '/v1/rule',
        json={
            'resource_key': 'public-access-resource',
            'principal': edi_id.JANE,
            'permission': 'read',
        },
    )
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN
    response = jane_client.post(
        '/v1/rule',
        json={
            'resource_key': 'public-access-resource',
            'principal': edi_id.JOHN,
            'permission': 'read',
        },
    )
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN

    # tests.sample.assert_match(response.json(), 'create_rule_by_owner.json')


# async def test_read_top_level_resource_with_valid_token(populated_dbi, john_client):
#     """readResource()
#     Successful call on top level resource -> The resource with the given resource_key, parent is
#     None.
#     """
#     # "key": "623e07e2ab7c400eab9b572e9abc3733",
#     # "label": "edi.7842.1",
#
#     # profile:
#     #       "edi_id": "EDI-147dd745c653451d9ef588aeb1d6a188",
#     #       "email": "john@smith.com",
#     #       "email_notifications": false,
#     #       "common_name": "John Smith",
#     #       "has_avatar": false,
#     #       "id": 4,
#     #       "privacy_policy_accepted": false,
#     #       "privacy_policy_accepted_date": null
#
#     # principal:
#     #       "id": 5,
#     #       "subject_id": 4,
#     #       "subject_type": "PROFILE"
#     #
#     # rule:
#     #       "id": 72,
#     #       "permission": "READ",
#     #       "principal_id": 5,
#     #       "resource_id": 62
#     #
#     #       "id": 482,
#     #       "permission": "CHANGE",
#     #       "principal_id": 5,
#     #       "resource_id": 341
#     #
#     # resource:
#     #         "id": 341,
#     #         "key": "2b22d840a07643d897588820343f8ac3",
#     #         "label": "edi.8233.4",
#     #         "parent_id": null,
#     #         "type": "package"
#
#     response = john_client.get('/v1/resource/2b22d840a07643d897588820343f8ac3')
#     assert response.status_code == starlette.status.HTTP_200_OK
#     tests.sample.assert_match(response.json(), 'read_top_level_resource_with_valid_token.json')
#
#
# async def test_read_child_resource_with_valid_token(john_client):
#     """readResource()
#     Successful call on child resource -> The resource with the given resource_key, with correct
#     EDI-ID for the parent.
#     """
#     response = john_client.get('/v1/resource/9aad4c65801f4feb9373e7b3281955cf')
#     assert response.status_code == starlette.status.HTTP_200_OK
#     tests.sample.assert_match(response.json(), 'read_child_resource_with_valid_token.json')
#
#
# async def test_read_resource_by_non_owner(populated_dbi, john_client, jane_client):
#     """readResource()
#     Call by non-owner (no changePermission ACR on resource) -> 403 Forbidden
#     """
#     # John creates a resource, and becomes the owner
#     john_client.post(
#         '/v1/resource',
#         json={
#             'resource_key': 'john-resource-key',
#             'resource_label': 'Resource created by John Smith',
#             'resource_type': 'testResource',
#             'parent_resource_key': None,
#         },
#     )
#     # Jane tries to access John's resource without having any ACRs on the resource
#     response = jane_client.get('/v1/resource/john-resource-key')
#     assert response.status_code == starlette.status.HTTP_403_FORBIDDEN
#
#
# async def test_read_resource_tree_1(john_client):
#     """readResourceTree()
#     Successful call on resource at level-2 in the tree
#     -> Full tree of resources that includes the given resource.
#     """
#     # Get a level-2 child resource (quality_report.xml, metadata)
#     # response = john_client.get('/v1/resource/2b22d840a07643d897588820343f8ac3')
#     response = john_client.get('/v1/resource/tree/2b22d840a07643d897588820343f8ac3')
#     assert response.status_code == starlette.status.HTTP_200_OK
#     tests.sample.assert_match(response.json(), 'read_resource_tree_1.json')
