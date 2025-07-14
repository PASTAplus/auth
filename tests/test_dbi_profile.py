"""Tests for profile management in the database interface
"""

import pytest
import tests.utils

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(30),
]

EDI_ID = 'EDI-00000000000000000000000000000000'


async def test_create_profile(populated_dbi):
    profile_row = await populated_dbi.create_profile(
        common_name='Common Name',
        edi_id=EDI_ID,
    )
    assert profile_row.edi_id == EDI_ID
    assert profile_row.common_name == 'Common Name'


async def test_get_profile_by_edi_id(populated_dbi):
    await populated_dbi.create_profile(
        common_name='Common Name',
        edi_id=EDI_ID,
    )
    profile_row = await populated_dbi.get_profile(EDI_ID)
    assert profile_row.edi_id == EDI_ID
    assert profile_row.common_name == 'Common Name'
