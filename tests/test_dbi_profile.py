"""Tests for profile management in the database interface"""

import pytest
import sqlalchemy.exc

import db.models.profile

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(30),
]

EDI_ID = 'EDI-00000000000000000000000000000000'


async def test_create_profile(populated_dbi):
    profile_row = await populated_dbi.create_profile(
        idp_name=db.models.profile.IdpName.SKELETON,
        common_name='Common Name',
        edi_id=EDI_ID,
    )
    assert profile_row.edi_id == EDI_ID
    assert profile_row.common_name == 'Common Name'


async def test_create_profile_duplicate_idp(populated_dbi):
    await populated_dbi.create_profile(
        idp_name=db.models.profile.IdpName.GOOGLE,
        idp_uid='test_uid',
        common_name='Common Name',
        email='test@test.com',
        has_avatar=False,
    )
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await populated_dbi.create_profile(
            idp_name=db.models.profile.IdpName.GOOGLE,
            idp_uid='test_uid',
            common_name='Common Name',
            email='test@test.com',
            has_avatar=False,
        )


async def test_get_profile_by_edi_id(populated_dbi):
    await populated_dbi.create_profile(
        idp_name=db.models.profile.IdpName.GOOGLE,
        common_name='Common Name',
        edi_id=EDI_ID,
    )
    profile_row = await populated_dbi.get_profile(EDI_ID)
    assert profile_row.edi_id == EDI_ID
    assert profile_row.common_name == 'Common Name'
