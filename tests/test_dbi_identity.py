"""Tests for identity management in the database interface
"""
import pytest
import sqlalchemy.exc


pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(20),
]


def test_create_identity(db):
    profile_row = db.create_profile(common_name='Given Family')
    identity = db.create_identity(
        profile_row,
        idp_name=db.models.identity.IdpName.GOOGLE,
        uid='test_uid',
        email='test@test.com',
    )
    assert identity is not None
    assert identity.uid == 'test_uid'
    assert identity.email == 'test@test.com'
    assert identity.edi_token == 'test_token'


def test_create_identity_duplicate_idp(db):
    profile_row = db.create_profile(common_name='Given Family')
    db.create_identity(profile_row, idp_name=db.models.identity.IdpName.GOOGLE, uid='test_uid')
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db.create_identity(profile_row, idp_name=db.models.identity.IdpName.GOOGLE, uid='test_uid')


def test_create_identity_duplicate_idp_with_unique_uid(db):
    """We can have multiple identities with the same IDP as long as the UID is unique,
    meaning the user has multiple accounts with the IdP"""
    profile_row = db.create_profile(common_name='Given Family')
    db.create_identity(profile_row, idp_name=db.models.identity.IdpName.GOOGLE, uid='test_uid_1')
    db.create_identity(profile_row, idp_name=db.models.identity.IdpName.GOOGLE, uid='test_uid_2')
