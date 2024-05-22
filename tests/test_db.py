import webapp.user_db


def test_create_db_instance(client, db_session):
    user_db = webapp.user_db.UserDb(db_session)
    assert user_db is not None


def test_create_profile(client, db_session):
    user_db = webapp.user_db.UserDb(db_session)
    user = user_db.create_profile("test_user")
    assert user is not None

def test_get_profile(client, db_session):
    user_db = webapp.user_db.UserDb(db_session)
    user_db.create_profile("test_user")
    user = user_db.get_profile("test_user")
    assert user is not None


