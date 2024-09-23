import re
import sqlite3

import pytest
import sqlalchemy.exc

import webapp.db


def _check_urid(urid):
    assert re.match(r'PASTA-[\da-f]{32}$', urid)


def test_create_db_instance(db):
    assert db is not None


def test_get_new_urid(db):
    urid = db.get_new_urid()
    _check_urid(urid)


def test_create_profile(db):
    profile_row = db.create_profile(given_name='Given1', family_name='Family1')
    _check_urid(profile_row.urid)


def test_get_profile(db):
    profile_row = db.create_profile(given_name='Given2', family_name='Family2')
    assert profile_row is not None
    assert profile_row.given_name == 'Given2'
    assert profile_row.family_name == 'Family2'


def test_create_identity_invalid_idp(db):
    """Attempt to create an identity with an invalid IdP."""
    profile_row = db.create_profile(given_name='Given', family_name='Family')
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db.create_identity(profile_row, idp_name='invalid_idp', uid='test_uid')


def test_create_identity(db):
    profile_row = db.create_profile(given_name='Given', family_name='Family')
    identity = db.create_identity(
        profile_row,
        idp_name='google',
        uid='test_uid',
        email='test@test.com',
        pasta_token='test_token',
    )
    assert identity is not None
    assert identity.uid == 'test_uid'
    assert identity.email == 'test@test.com'
    assert identity.pasta_token == 'test_token'


def test_create_identity_duplicate_idp(db):
    profile_row = db.create_profile(given_name='Given', family_name='Family')
    db.create_identity(profile_row, idp_name='google', uid='test_uid')
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        db.create_identity(profile_row, idp_name='google', uid='test_uid')


def test_create_identity_duplicate_idp_with_unique_uid(db):
    """We can have multiple identities with the same IDP as long as the UID is unique,
    meaning the user has multiple accounts with the IdP"""
    profile_row = db.create_profile(given_name='Given', family_name='Family')
    db.create_identity(profile_row, idp_name='google', uid='test_uid_1')
    db.create_identity(profile_row, idp_name='google', uid='test_uid_2')


def test_create_or_update_profile_and_identity(db):
    identity_row = db.create_or_update_profile_and_identity(
        given_name='Given',
        family_name='Family',
        idp_name='google',
        uid='test_uid',
        email='test@test.test',
        has_avatar=False,
        pasta_token='test_token',
    )
    assert identity_row is not None
    assert identity_row.uid == 'test_uid'
    assert identity_row.email == 'test@test.test'
    assert identity_row.pasta_token == 'test_token'


def test_get_all_profiles_with_identity_mapping(db):
    for i in range(10):
        db.create_or_update_profile_and_identity(
            given_name='Given',
            family_name='Family',
            idp_name='google',
            uid=f'test_uid_{i}',
            email='test@test.test',
            pasta_token=f'test_token_{i}',
            has_avatar=False,
        )
    for i, profile in enumerate(db.get_all_profiles()):
        assert profile is not None
        assert profile.given_name == 'Given'
        assert profile.identities[0].uid == f'test_uid_{i}'
