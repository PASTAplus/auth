"""Tests for group and group member management in the database interface"""

import logging

import pytest

import db.models.permission
import db.resource_tree

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(40),
]

# Random non-existing EDI-IDs
EDI_ID_1 = 'EDI-834b647f2044922a4723df5795268261e80e09fd'

log = logging.getLogger(__name__)


async def test_create_group(populated_dbi, john_profile_row):
    """Create a new group -> new group, and a new resource with CHANGE for the creator"""
    await populated_dbi.create_group(john_profile_row, 'Test Group', 'Group Description')
    # TODO: Verify the created group and resource

async def test_rule(populated_dbi, john_profile_row):
    group_row, resource_row = await populated_dbi.create_group(
        john_profile_row, 'Test Group', 'Group Description'
    )
    principal_row = await populated_dbi.get_principal_by_profile(john_profile_row)
    await populated_dbi.create_or_update_rule(
        resource_row, principal_row, db.models.permission.PermissionLevel.WRITE
    )
    rule_row = await populated_dbi.get_rule(resource_row, principal_row)
    assert rule_row is not None


async def test_is_existing_edi_id_for_group(populated_dbi, john_profile_row):
    assert not await populated_dbi.is_existing_edi_id(EDI_ID_1)
    # Add a group with the EDI-ID
    new_group_row = db.models.group.Group(
        edi_id=EDI_ID_1,
        profile=john_profile_row,
        name='Test Group',
    )
    populated_dbi._session.add(new_group_row)
    await populated_dbi.flush()
    assert await populated_dbi.is_existing_edi_id(EDI_ID_1)
