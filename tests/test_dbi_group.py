"""Tests for group and group member management in the database interface"""

import tests.sample
import logging

import pytest
import sqlalchemy

import db.models.permission
import db.resource_tree
import tests.edi_id
import tests.sample


pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(40),
]

log = logging.getLogger(__name__)


async def test_create_group(populated_dbi, john_profile_row):
    """Create a new group -> new group, and a new resource with CHANGE for the creator"""
    await populated_dbi.create_group(john_profile_row, 'Test Group', 'Group Description')


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
