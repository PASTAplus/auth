"""Tests for v1 group management APIs"""

import logging

import pytest

import tests.edi_id
import tests.sample
import tests.utils

from config import Config

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(100),
]

#
# createGroup()
#


async def test_create_group(populated_dbi, service_client, john_client):
    """createGroup()
    Successful call -> A new group is created.
    """
    group_test_name = 'test_create_group() - Test Group'
    group_test_desc = 'test_create_group() - Description of Test Group'
    response = john_client.post(
        '/v1/group',
        json={
            'title': group_test_name,
            'description': group_test_desc,
        },
    )
    assert response.status_code == 200
    response_dict = response.json()
    group_edi_id = response_dict.get('group_edi_id')
    tests.sample.assert_match(response_dict, 'create_group.json', clobber=True)
    group_row = await populated_dbi.get_group(group_edi_id)
    assert group_row is not None
    assert group_row.name == group_test_name
    assert group_row.description == group_test_desc


async def test_read_group(populated_dbi, service_client, john_client, john_profile_row):
    """readGroup()
    Successful call -> The group information is returned.
    """
    # John creates a new group
    group_test_name = 'test_read_group() - Test Group'
    group_test_desc = 'test_read_group() - Description of Test Group'
    response = john_client.post(
        '/v1/group',
        json={
            'title': group_test_name,
            'description': group_test_desc,
        },
    )
    assert response.status_code == 200
    response_dict = response.json()
    group_edi_id = response_dict.get('group_edi_id')
    response = john_client.get(f'/v1/group/{group_edi_id}')
    assert response.status_code == 200
    response_dict = response.json()
    tests.sample.assert_match(response_dict, 'read_group.json', clobber=True)


async def test_delete_group(populated_dbi, service_client, john_client, john_profile_row):
    """deleteGroup()
    Successful call -> The group is deleted.
    """
    # John creates a new group
    response = john_client.post(
        '/v1/group',
        json={
            'title': 'test_delete_group() - title',
            'description': 'test_delete_group() - description',
        },
    )
    assert response.status_code == 200
    response_dict = response.json()
    group_edi_id = response_dict.get('group_edi_id')
    await populated_dbi.flush()
    # Now, John deletes the group
    response = john_client.delete(f'/v1/group/{group_edi_id}')
    assert response.status_code == 200
    response_dict = response.json()
    tests.sample.assert_match(response_dict, 'delete_group.json', clobber=True)


#
# addGroupMember()
#


async def test_add_group_member(populated_dbi, service_client, john_profile_row):
    """addGroupMember()
    Successful call -> The given profile becomes a member of the group.
    """
    response = service_client.post(
        f'/v1/group/{Config.VETTED_GROUP_EDI_ID}/{john_profile_row.edi_id}',
    )
    assert response.status_code == 200
    group_edi_id = response.json().get('group')
    await populated_dbi.flush()
    response = service_client.get(f'/v1/group/{group_edi_id}')
    assert response.status_code == 200
    response_dict = response.json()
    tests.sample.assert_match(response_dict, 'add_group_member.json')


async def test_add_group_member_already_in_group(populated_dbi, service_client, john_profile_row):
    """addGroupMember()
    Call with a profile that is already a member of the group -> 200 OK, with message indicating
    that the profile is already in the group.
    """
    response = service_client.post(
        f'/v1/group/{Config.VETTED_GROUP_EDI_ID}/{john_profile_row.edi_id}',
    )
    assert response.status_code == 200
    tests.utils.dump_response(response)
    # Even though a regular call to an API endpoint will be in a separate request/response cycle
    # and commited as a separate transaction, the TestClient only simulates this, and does not
    # actually commit the transaction, so we need to flush the changes to the database.
    await populated_dbi.flush()
    # Idempotent call with the same profile should return 200 OK again
    response = service_client.post(
        f'/v1/group/{Config.VETTED_GROUP_EDI_ID}/{john_profile_row.edi_id}',
    )
    assert response.status_code == 200
    response_dict = response.json()
    tests.sample.assert_match(response_dict, 'add_group_member_already_in_group.json')


#
# removeGroupMember()
#


async def test_remove_group_member(populated_dbi, service_client, john_profile_row):
    """removeGroupMember()
    Successful call -> The given profile is removed from the group.
    """
    # First, add John to the Vetted group
    response = service_client.post(
        f'/v1/group/{Config.VETTED_GROUP_EDI_ID}/{john_profile_row.edi_id}',
    )
    assert response.status_code == 200
    await populated_dbi.flush()
    # Now, remove John from the Vetted group
    response = service_client.delete(
        f'/v1/group/{Config.VETTED_GROUP_EDI_ID}/{john_profile_row.edi_id}',
    )
    assert response.status_code == 200
    response_dict = response.json()
    tests.sample.assert_match(response_dict, 'remove_group_member.json')
    await populated_dbi.flush()
    # Verify that John is no longer a member of the group
    response = service_client.get(f'/v1/group/{Config.VETTED_GROUP_EDI_ID}')
    assert response.status_code == 200
    response_dict = response.json()
    assert john_profile_row.edi_id not in response_dict.get('members', [])


async def test_remove_group_member_not_in_group(populated_dbi, service_client, john_profile_row):
    """removeGroupMember()
    Call with a profile that is not a member of the group -> 200 OK, with message indicating
    that the profile is not in the group.
    """
    response = service_client.delete(
        f'/v1/group/{Config.VETTED_GROUP_EDI_ID}/{john_profile_row.edi_id}',
    )
    assert response.status_code == 404
    response_dict = response.json()
    tests.sample.assert_match(response_dict, 'remove_group_member_not_in_group.json')
