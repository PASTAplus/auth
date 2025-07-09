"""Tests for profile management in the database interface
"""

import pytest

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(30),
]


def test_create_profile(db):
    profile_row = db.create_profile(common_name='Given1 Family1')
    _check_edi_id(profile_row.edi_id)


def test_get_profile(db):
    profile_row = db.create_profile(common_name='Given2 Family2')
    assert profile_row is not None
    assert profile_row.common_name == 'Given2 Family2'


def test_create_or_update_profile_and_identity(db):
    identity_row = db.create_or_update_profile_and_identity(
        common_name='Given Family',
        idp_name=db.models.identity.IdpName.GOOGLE,
        uid='test_uid',
        email='test@test.test',
        has_avatar=False,
    )
    assert identity_row is not None
    assert identity_row.uid == 'test_uid'
    assert identity_row.email == 'test@test.test'
    assert identity_row.edi_token == 'test_token'


def test_get_all_profiles_with_identity_mapping(db):
    for i in range(10):
        db.create_or_update_profile_and_identity(
            common_name='Given Family',
            idp_name=db.models.identity.IdpName.GOOGLE,
            uid=f'test_uid_{i}',
            email='test@test.test',
            has_avatar=False,
            old_token=None,
        )
    for i, profile in enumerate(db.get_all_profiles()):
        assert profile is not None
        assert profile.common_name == 'Given Family'
        assert profile.identities[0].uid == f'test_uid_{i}'


