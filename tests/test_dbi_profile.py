"""Tests for profile management in the database interface"""

import pytest
import sqlalchemy.exc

import db.models.profile

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(30),
]

# Random non-existing EDI-IDs
EDI_ID_1 = 'EDI-834b647f2044922a4723df5795268261e80e09fd'

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
    )
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await populated_dbi.create_profile(
            idp_name=db.models.profile.IdpName.GOOGLE,
            idp_uid='test_uid',
            common_name='Common Name',
            email='test@test.com',
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


async def test_is_existing_edi_id_for_profile(populated_dbi, john_profile_row):
    assert not await populated_dbi.is_existing_edi_id(EDI_ID_1)
    # Add a profile with the EDI-ID
    new_profile_row = db.models.profile.Profile(
        idp_name=db.models.profile.IdpName.SKELETON,
        edi_id=EDI_ID_1,
        common_name='Common Name',
    )
    populated_dbi._session.add(new_profile_row)
    await populated_dbi.flush()
    assert await populated_dbi.is_existing_edi_id(EDI_ID_1)


