import re
import sqlite3

import pytest
import sqlalchemy.exc

import db
import db.models.identity


def _check_edi_id(edi_id):
    assert re.match(r'EDI-[\da-f]{32}$', edi_id)


def test_create_db_instance(db):
    assert db is not None


def test_get_new_edi_id(db):
    edi_id = db.get_new_edi_id()
    _check_edi_id(edi_id)


def test_create_profile(db):
    profile_row = db.create_profile(common_name='Given1 Family1')
    _check_edi_id(profile_row.edi_id)


def test_get_profile(db):
    profile_row = db.create_profile(common_name='Given2 Family2')
    assert profile_row is not None
    assert profile_row.common_name == 'Given2 Family2'


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
    assert identity.pasta_token == 'test_token'


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
    assert identity_row.pasta_token == 'test_token'


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
