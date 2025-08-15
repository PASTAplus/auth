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
# addGroupMember()
#


async def test_add_group_member(service_client, john_profile_row):
    """addGroupMember()
    Successful call -> The given profile becomes a member of the group.
    """
    response = service_client.post(
        f'/v1/group/{Config.VETTED_GROUP_EDI_ID}/{john_profile_row.edi_id}',
    )
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
    # Even though a regular call to an API endpoint will be in a separate request/response cycle,
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
