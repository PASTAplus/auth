"""Tests for group and group member management in the database interface"""

import logging

import pytest

import db.models.profile
import db.models.group
import db.models.permission
import db.resource_tree

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(40),
]

log = logging.getLogger(__name__)

# Random non-existing EDI-IDs
EDI_ID_1 = 'EDI-834b647f2044922a4723df5795268261e80e09fd'

async def test_is_existing_edi_id_for_profile(populated_dbi, john_profile_row):
    assert not await populated_dbi.is_existing_edi_id(EDI_ID_1)
    # Add a profile with the EDI-ID
    new_profile_row = db.models.profile.Profile(
        edi_id=EDI_ID_1,
        common_name='Common Name',
    )
    populated_dbi._session.add(new_profile_row)
    await populated_dbi.flush()
    assert await populated_dbi.is_existing_edi_id(EDI_ID_1)


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
