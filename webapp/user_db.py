import datetime
import sqlite3
import uuid

import daiquiri
import fastapi
import sqlalchemy.event
import sqlalchemy.orm
import sqlalchemy.pool

import config

log = daiquiri.getLogger(__name__)

Base = sqlalchemy.orm.declarative_base()

engine = sqlalchemy.create_engine(
    'sqlite:///' + config.Config.DB_PATH.as_posix(),
    echo=config.Config.LOG_DB_QUERIES,
    connect_args={
        # 'check_same_thread': False,
    },
)

SessionLocal = sqlalchemy.orm.sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)

# Enable foreign key checking in SQlite
@sqlalchemy.event.listens_for(sqlalchemy.pool.Pool, "connect")
def _on_connect(dbapi_con, _connection_record):
    if isinstance(dbapi_con, sqlite3.Connection):
        dbapi_con.execute('PRAGMA foreign_keys=ON')


def get_db():
    db = SessionLocal()
    try:
        # yield None
        yield db
    finally:
        db.close()


def udb(session: sqlalchemy.orm.Session = fastapi.Depends(get_db)):
    try:
        yield UserDb(session)
    finally:
        session.close()


class UserDb:
    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session

    def get_all_uids(self):
        query = self.session.query(Identity.uid)
        uids = [row[0] for row in query.all()]
        return uids

    def get_all_profiles(self):
        query = self.session.query(Profile.name)
        return [row[0] for row in query.all()]

    @staticmethod
    def get_new_urid():
        return f'PASTA-{uuid.uuid4().hex}'

    def create_profile(self, given_name: str = None, family_name: str = None):
        urid = UserDb.get_new_urid()
        new_profile = Profile(
            urid=urid,
            given_name=given_name,
            family_name=family_name,
        )
        self.session.add(new_profile)
        self.session.commit()
        return urid

    def get_profile(self, urid):
        query = self.session.query(Profile)
        profile = query.filter(Profile.urid == urid).first()
        return profile

    def has_profile(self, urid):
        query = self.session.query(Profile)
        profile = query.filter(Profile.urid == urid).first()
        return profile is not None

    def create_identity(self, urid: str, idp: str, uid: str, email: str = None):
        #     uid = sqlalchemy.Column(sqlalchemy.String, primary_key=True)
        #     email = sqlalchemy.Column(sqlalchemy.String, nullable=True)
        #     token = sqlalchemy.Column(sqlalchemy.String, nullable=True)
        #     first_auth = sqlalchemy.Column(
        #         sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
        #     )
        #     last_auth = sqlalchemy.Column(
        #         sqlalchemy.DateTime,
        #         nullable=False,
        #         default=datetime.datetime.now,
        #         onupdate=datetime.datetime.now,
        #     )
        #     profile = sqlalchemy.orm.relationship('Profile', backref='identities')
        new_identity = Identity(urid=urid, idp=idp, uid=uid, email=email)
        self.session.add(new_identity)
        self.session.commit()
        return new_identity

    # def get_profile(self, name):
    #     query = self.session.query(Profile)
    #     profile = query.filter(Profile.name == name).first()
    #     return profile
    #
    # def get_all_uids(self):
    #     query = self.session.query(Identity.uid)
    #     uids = [row[0] for row in query.all()]
    #     return uids
    #
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
    #
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


#
# Tables
#


class Profile(Base):
    __tablename__ = 'profile'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    urid = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    given_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    family_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    privacy_policy_accepted = sqlalchemy.Column(
        sqlalchemy.Boolean(), nullable=False, default=False
    )
    privacy_policy_accepted_date = sqlalchemy.Column(
        sqlalchemy.DateTime(), nullable=True
    )


class Identity(Base):
    __tablename__ = 'identity'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # Foreign key to Profile.urid
    urid = sqlalchemy.Column(
        sqlalchemy.String, sqlalchemy.ForeignKey('profile.urid'), nullable=False
    )
    # The IdP's user ID
    # TODO: namespaced with the IdP's name?
    idp = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    uid = sqlalchemy.Column(sqlalchemy.String, nullable=False)
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

    profile = sqlalchemy.orm.relationship('Profile', backref='identities')

    __table_args__ = (
        # Ensure that idp and uid are unique together (each IdP has its own namespace for unique identifiers)
        sqlalchemy.UniqueConstraint('idp', 'uid', name='idp_uid_unique'),
        # Ensure that the idp is the name of one of our supported IdPs
        sqlalchemy.CheckConstraint(
            "idp IN ('github', 'google', 'ldap', 'microsoft', 'orcid')",
            name='idp_check'
        ),
    )
