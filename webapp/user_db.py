import datetime

import daiquiri
import flask
import sqlalchemy.orm

log = daiquiri.getLogger(__name__)
Base = sqlalchemy.orm.declarative_base()
# Base = sqlalchemy.ext.declarative.declarative_base()


class Profile(Base):
    __tablename__ = 'profile'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String)
    privacy_policy_accepted = sqlalchemy.Column(
        sqlalchemy.Boolean(), nullable=False, default=False
    )
    privacy_policy_accepted_date = sqlalchemy.Column(
        sqlalchemy.DateTime(), nullable=True
    )


class Identity(Base):
    __tablename__ = 'identity'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    uid = sqlalchemy.Column(sqlalchemy.String, primary_key=True)
    email = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    token = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    first_auth = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    last_auth = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
    profile_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('profile.id')
    )
    profile = sqlalchemy.orm.relationship("Profile")


class UserDb:
    def __init__(self, db_session: sqlalchemy.orm.Session = None):
        self.session = db_session or flask.g.session

    # def set_accepted(self, uid: str):
    #     query = self.session.query(User)
    #     user = query.filter(User.uid == uid).first()
    #     user.privacy_acceptance = True
    #     user.date_accepted = datetime.datetime.now()
    #     self.session.commit()
    #
    # def is_privacy_policy_accepted(self, uid: str) -> bool:
    #     query = self.session.query(User)
    #     user = query.filter(User.uid == uid).first()
    #     return user.privacy_acceptance
    #
    # def set_cname(self, uid: str, cname: str):
    #     query = self.session.query(User)
    #     user = query.filter(User.uid == uid).first()
    #     user.cname = cname
    #     self.session.commit()
    #
    # def get_cname(self, uid: str) -> str:
    #     query = self.session.query(User)
    #     user = query.filter(User.uid == uid).first()
    #     return user.cname
    #
    # def set_email(self, uid: str, email: str):
    #     query = self.session.query(User)
    #     user = query.filter(User.uid == uid).first()
    #     user.email = email
    #     self.session.commit()
    #
    # def get_email(self, uid: str) -> str:
    #     query = self.session.query(User)
    #     user = query.filter(User.uid == uid).first()
    #     return user.email
    #
    # def set_token(self, uid: str, token: str):
    #     query = self.session.query(User)
    #     user = query.filter(User.uid == uid).first()
    #     user.token = token
    #     self.session.commit()
    #
    # def get_token(self, uid: str) -> str:
    #     query = self.session.query(User)
    #     user = query.filter(User.uid == uid).first()
    #     return user.token
    #
    # def set_user(self, uid: str, token: str, cname: str):
    #     if self.get_user(uid=uid) is None:
    #         user = User(uid=uid, token=token, cname=cname)
    #         self.session.add(user)
    #         self.session.commit()
    #     else:  # Set only token if user exists
    #         self.set_token(uid=uid, token=token)
    #
    # def get_user(self, uid: str):
    #     query = self.session.query(User)
    #     user = query.filter(User.uid == uid).first()
    #     return user
    #
    # def purge_user(self, uid: str):
    #     query = self.session.query(User)
    #     user = query.filter(User.uid == uid).first()
    #     self.session.delete(user)
    #     self.session.commit()

    def create_profile(self, name):
        new_profile = Profile(name=name)
        self.session.add(new_profile)
        self.session.commit()
        return new_profile

    def get_profile(self, name):
        query = self.session.query(Profile)
        profile = query.filter(Profile.name == name).first()
        return profile

    # def create_user(self):
    #
    #
    #     name = sqlalchemy.Column(sqlalchemy.String)
    #     privacy_policy_accepted = sqlalchemy.Column(
    #         sqlalchemy.Boolean(), nullable=False, default=False
    #     )
    #     privacy_policy_accepted_date = sqlalchemy.Column(
    #         sqlalchemy.DateTime(), nullable=True
    #     )
