""":Mod: user_db

:Synopsis:

:Author:
    servilla

:Created:
    10/16/19
"""
from datetime import datetime

import daiquiri
from sqlalchemy import Column, String, DateTime, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from webapp.config import Config

log = daiquiri.getLogger(__name__)

Base = declarative_base()


class User(Base):
    __tablename__ = "user"

    uid = Column(String(), primary_key=True)
    token = Column(String(), nullable=True)
    cname = Column(String(), nullable=True)
    first_auth = Column(DateTime(), nullable=False, default=datetime.now)
    last_auth = Column(
        DateTime(), nullable=False, default=datetime.now, onupdate=datetime.now
    )
    email = Column(String(), nullable=True)
    privacy_acceptance = Column(Boolean(), nullable=False, default=False)
    date_accepted = Column(DateTime(), nullable=True)


class UserDb(object):
    def __init__(self, db: str = Config.DB):
        self.db = db
        engine = create_engine("sqlite:///" + self.db)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def set_accepted(self, uid: str):
        query = self.session.query(User)
        user = query.filter(User.uid == uid).first()
        user.privacy_acceptance = True
        user.date_accepted = datetime.now()
        self.session.commit()

    def is_privacy_policy_accepted(self, uid: str) -> bool:
        query = self.session.query(User)
        user = query.filter(User.uid == uid).first()
        return user.privacy_acceptance

    def set_cname(self, uid: str, cname: str):
        query = self.session.query(User)
        user = query.filter(User.uid == uid).first()
        user.cname = cname
        self.session.commit()

    def get_cname(self, uid: str) -> str:
        query = self.session.query(User)
        user = query.filter(User.uid == uid).first()
        return user.cname

    def set_email(self, uid: str, email: str):
        query = self.session.query(User)
        user = query.filter(User.uid == uid).first()
        user.email = email
        self.session.commit()

    def get_email(self, uid: str) -> str:
        query = self.session.query(User)
        user = query.filter(User.uid == uid).first()
        return user.email

    def set_token(self, uid: str, token: str):
        query = self.session.query(User)
        user = query.filter(User.uid == uid).first()
        user.token = token
        self.session.commit()

    def get_token(self, uid: str) -> str:
        query = self.session.query(User)
        user = query.filter(User.uid == uid).first()
        return user.token

    def set_user(self, uid: str, token: str, cname: str):
        if self.get_user(uid=uid) is None:
            user = User(uid=uid, token=token, cname=cname)
            self.session.add(user)
            self.session.commit()
        else:  # Set only token if user exists
            self.set_token(uid=uid, token=token)

    def get_user(self, uid: str):
        query = self.session.query(User)
        user = query.filter(User.uid == uid).first()
        return user

    def purge_user(self, uid: str):
        query = self.session.query(User)
        user = query.filter(User.uid == uid).first()
        self.session.delete(user)
        self.session.commit()
