"""Tests for identity management in the database interface"""

import pytest
import sqlalchemy.exc
import db.models.identity


pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(20),
]


async def test_create_identity_success(populated_dbi):
    profile_row = await populated_dbi.create_profile(common_name='Common Name')
    identity = await populated_dbi.create_identity(
        profile_row,
        idp_name=db.models.identity.IdpName.GOOGLE,
        idp_uid='test_uid',
        common_name='Common Name',
        email='test@test.com',
        has_avatar=False,
    )
    assert identity is not None
    assert identity.idp_uid == 'test_uid'


async def test_create_identity_duplicate_idp(populated_dbi):
    profile_row = await populated_dbi.create_profile(common_name='Common Name')
    await populated_dbi.create_identity(
        profile_row,
        idp_name=db.models.identity.IdpName.GOOGLE,
        idp_uid='test_uid',
        common_name='Common Name',
        email='test@test.com',
        has_avatar=False,
    )
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await populated_dbi.create_identity(
            profile_row,
            idp_name=db.models.identity.IdpName.GOOGLE,
            idp_uid='test_uid',
            common_name='Common Name',
            email='test@test.com',
            has_avatar=False,
        )


async def test_create_identity_multiple_idp_with_unique_uid(populated_dbi):
    """We can have multiple identities with the same IDP as long as the UID is unique,
    meaning the user has multiple accounts with the IdP"""
    profile_row = await populated_dbi.create_profile(common_name='Common Name')
    await populated_dbi.create_identity(
        profile_row,
        idp_name=db.models.identity.IdpName.GOOGLE,
        idp_uid='test_uid_1',
        common_name='Common Name',
        email='test@test.com',
        has_avatar=False,
    )
    await populated_dbi.create_identity(
        profile_row,
        idp_name=db.models.identity.IdpName.GOOGLE,
        idp_uid='test_uid_2',
        common_name='Common Name',
        email='test@test.com',
        has_avatar=False,
    )
