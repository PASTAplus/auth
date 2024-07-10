import re
import sqlite3

import pytest
import sqlalchemy.exc

import webapp.user_db


def _check_urid(urid):
    assert re.match(r'PASTA-[\da-f]{32}$', urid)


def test_create_db_instance(user_db):
    assert user_db is not None

    # user_db = webapp.user_db.UserDb(db_session)
    # user_db.create_profile()
    # assert user_db is not None


def test_get_new_urid(user_db):
    urid = user_db.get_new_urid()
    _check_urid(urid)


def test_create_profile(user_db):
    urid = user_db.create_profile(given_name='Given1', family_name='Family1')
    _check_urid(urid)


def test_get_profile(user_db):
    urid = user_db.create_profile(given_name='Given2', family_name='Family2')
    profile = user_db.get_profile(urid)
    assert profile is not None
    assert profile.given_name == 'Given2'
    assert profile.family_name == 'Family2'


# @pytest.mark.filterwarnings("ignore:sqlalchemy.exc.SAWarning")
def test_create_identity_invalid_urid(user_db):
    """Attempt to create an identity with an invalid URID."""
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        user_db.create_identity(urid='invalid_urid', idp='google', uid='test_uid')


def test_create_identity_invalid_idp(user_db):
    """Attempt to create an identity with an invalid IDP."""
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        urid = user_db.create_profile(given_name='Given1', family_name='Family1')
        user_db.create_identity(urid=urid, idp='invalid_idp', uid='test_uid')


def test_create_identity(user_db):
    urid = user_db.create_profile(given_name='Given1', family_name='Family1')
    identity = user_db.create_identity(urid=urid, idp='google', uid='test_uid')
    assert identity is not None
    assert identity.uid == 'test_uid'
    assert identity.email is None
    assert identity.token is None


def test_create_identity_duplicate_idp(user_db):
    urid = user_db.create_profile(given_name='Given1', family_name='Family1')
    user_db.create_identity(urid=urid, idp='google', uid='test_uid')
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        user_db.create_identity(urid=urid, idp='google', uid='test_uid')


def test_create_identity_duplicate_idp_with_unique_uid(user_db):
    """We can have multiple identities with the same IDP as long as the UID is unique,
    meaning the user has multiple accounts with the IdP"""
    urid = user_db.create_profile(given_name='Given1', family_name='Family1')
    user_db.create_identity(urid=urid, idp='google', uid='test_uid_1')
    user_db.create_identity(urid=urid, idp='google', uid='test_uid_2')


# def test_get_identity_list(user_db):
#     urid = user_db.create_profile(given_name='Given1', family_name='Family1')
#     user_db.create_identity(urid=urid, idp='google', uid='test_uid')
#     user_db.create_identity(urid=urid, idp='google', uid='test_uid')


# urid = user_db.create_profile(given_name='Given', family_name='Family')
# profile = user_db.get_profile(urid)

# assert profile is not None
# assert profile.given_name == 'Given'
# assert profile.family_name == 'Family'


#     user_db = webapp.user_db.UserDb(db_session)
#     user = user_db.create_profile("test_user")
#     assert user is not None

# def test_get_profile(client, db_session):
#     user_db = webapp.user_db.UserDb(db_session)
#     user_db.create_profile("test_user")
#     user = user_db.get_profile("test_user")
#     assert user is not None
