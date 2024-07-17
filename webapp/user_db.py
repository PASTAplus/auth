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


#
# Tables
#

Base = sqlalchemy.orm.declarative_base()


class Profile(Base):
    __tablename__ = 'profile'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # Our 'User Random ID' (urid) for the user. This is the primary key for the user in
    # our system.
    urid = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    # The user's given and family names. Initially set to the values provided by the
    # IdP.
    given_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    family_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The email address that the user has chosen as their contact email. Initially set
    # to the email address provided by the IdP.
    email = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # Initially false, then set to true when the user accepts the privacy policy.
    privacy_policy_accepted = sqlalchemy.Column(
        sqlalchemy.Boolean(), nullable=False, default=False
    )
    # The date when the user accepted the privacy policy.
    privacy_policy_accepted_date = sqlalchemy.Column(
        sqlalchemy.DateTime(), nullable=True
    )
    identities = sqlalchemy.orm.relationship('Identity', back_populates='profile')
    @property
    def full_name(self):
        return f'{self.given_name} {self.family_name}'



class Identity(Base):
    __tablename__ = 'identity'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # Identities have a many-to-one relationship with Profiles. This allows us to find
    # the one Profile that corresponds to a given Identity, and to find all Identities
    # that correspond to a given Profile. The latter is referenced via the backref
    # 'identities' in the Profile. The 'profile_id' declaration creates the physical
    # column in the table which tracks the relationship. Setting 'profile_id' nullable
    # to False forces the identity to be linked to an existing profile. The 'profile'
    # declaration specifies the relationship for use only in the ORM layer.
    profile_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('profile.id'), nullable=False
    )
    profile = sqlalchemy.orm.relationship('Profile', back_populates='identities')
    # Foreign key to Profile
    # profile_id = sqlalchemy.Column(
    #     sqlalchemy.Integer, sqlalchemy.ForeignKey('profile.id'), nullable=False
    # )
    # Our name for the IdP. Currently one of 'github', 'google', 'ldap', 'microsoft',
    # 'orcid'.
    # This acts as a namespace for the subject (sub) provided by the IdP.
    idp_name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    # The uid is the unique user ID provided by the IdP. The source of this value varies
    # with the IdP. E.g., for Google, it's the 'sub' (subject) and for ORCID, it's an
    # ORCID on URL form. The value is unique within the IdP's namespace. It is only
    # unique within our system when combined with the idp_name.
    uid = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    # The email address provided by the IdP. This will change if the user updates their
    # email address with the IdP.
    email = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The PASTA token that was issued to the client in the most recent successful
    # authentication with this identity. The token is always updated here after
    # successfully authenticating with the IdP, but is not issued to the user unless
    # they have also accepted the privacy policy.
    pasta_token = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The date and time of the first successful authentication with this identity.
    # The authentication is successful if # successfully authenticated by the IdP, even
    # if the user then does not accept the # privacy policy.
    first_auth = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    # The date and time of the most recent successful authentication with this identity.
    last_auth = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
    __table_args__ = (
        # Ensure that idp_name and uid are unique together (each IdP has its own
        # namespace for unique identifiers)
        sqlalchemy.UniqueConstraint('idp_name', 'uid', name='idp_name_uid_unique'),
        # Ensure that the idp_name is the name of one of our supported IdPs
        sqlalchemy.CheckConstraint(
            "idp_name IN ('github', 'google', 'ldap', 'microsoft', 'orcid')",
            name='idp_name_check',
        ),
    )

#
# DB setup
#

engine = sqlalchemy.create_engine(
    'sqlite:///' + config.Config.DB_PATH.as_posix(),
    echo=config.Config.LOG_DB_QUERIES,
    connect_args={
        # Allow multiple threads to access the database
        # This setup allows the SQLAlchemy engine to manage SQLite connections that can
        # safely be shared across threads, mitigating the "SQLite objects created in a
        # thread can only be used in that same thread" limitation.
        'check_same_thread': False,
    },
)

# TODO: Add some sort of switch for this
#Base.metadata.drop_all(engine)

# Create the tables in the database
Base.metadata.create_all(engine)

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
        yield db
    finally:
        db.close()


def udb(session: sqlalchemy.orm.Session = fastapi.Depends(get_db)):
    try:
        yield UserDb(session)
    finally:
        session.close()


#
# Interface
#


class UserDb:
    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session

    #
    # Profile and Identity
    #
    def create_or_update_profile_and_identity(
        self,
        # Profile (only used if a new profile is created)
        given_name: str,
        family_name: str,
        # Identity
        idp_name: str,
        uid: str,
        # email is always updated in the identity but only set in the profile if a new
        # profile is created.
        email: str,
        # The pasta token is always updated after successful authentication with the IdP.
        pasta_token: str,
    ) -> Identity:
        """Create or update a profile and identity.

        See the table definitions for Profile and Identity for more information on the
        fields.
        """
        identity_row = self.get_identity(idp_name=idp_name, uid=uid)
        if identity_row is None:
            profile_row = self.create_profile(
                given_name=given_name,
                family_name=family_name,
                email=email,
            )
            identity_row = self.create_identity(
                profile=profile_row,
                idp_name=idp_name,
                uid=uid,
                email=email,
                pasta_token=pasta_token,
            )
        else:
            assert identity_row.profile is not None
            assert identity_row.idp_name == idp_name
            assert identity_row.uid == uid
            # We do not update the profile if it exists, since the profile belongs to the
            # user, and they may update their profile with their own information.
            #
            # TODO: Before we provide a way for users to update their profile, we need to
            # make sure ezEML, and other clients, have moved to using the URID as the
            # primary key for the user.
            #
            # We update the email address in the identity row.
            # profile if the profile is new. So if the user has changed their email
            # address with the IdP, the new email address will be stored in the identity
            # row, but the profile will retain the original email address.
            identity_row.email = email
            identity_row.pasta_token = pasta_token
            self.session.commit()

        return identity_row

    def create_profile(
        self, given_name: str = None, family_name: str = None, email: str = None
    ):
        new_profile = Profile(
            urid=UserDb.get_new_urid(),
            given_name=given_name,
            family_name=family_name,
            email=email,
        )
        self.session.add(new_profile)
        self.session.commit()
        return new_profile

    def get_profile(self, urid):
        query = self.session.query(Profile)
        profile = query.filter(Profile.urid == urid).first()
        return profile

    def has_profile(self, urid):
        return self.get_profile(urid) is not None

    def is_privacy_policy_accepted(self, urid: str) -> bool:
        return self.get_profile(urid).privacy_policy_accepted

    def set_privacy_policy_accepted(self, urid: str):
        self.get_profile(urid).privacy_policy_accepted = True
        self.session.commit()

    #
    # Identity
    #

    # def get_or_create_identity(self, idp_name: str, uid: str, email: str = None):
    #     identity = self.get_identity(idp_name, uid)
    #     if identity is None:
    #         urid = self.get_new_urid()
    #         identity = self.create_identity(urid, idp_name, uid, email)
    #     return identity.urid

    def create_identity(
        self,
        profile,
        idp_name: str,
        uid: str,
        email: str = None,
        pasta_token: str = None,
    ):
        """Create a new identity for a given profile."""
        new_identity = Identity(
            profile=profile,
            idp_name=idp_name,
            uid=uid,
            email=email,
            pasta_token=pasta_token,
        )
        self.session.add(new_identity)
        self.session.commit()
        return new_identity

    def get_identity(self, idp_name: str, uid: str):
        query = self.session.query(Identity)
        identity = query.filter(
            Identity.idp_name == idp_name, Identity.uid == uid
        ).first()
        return identity

    @staticmethod
    def get_new_urid():
        return f'PASTA-{uuid.uuid4().hex}'

    # def get_all_uids(self):
    #     query = self.session.query(Identity.uid)
    #     uids = [row[0] for row in query.all()]
    #     return uids
    #
    # def get_all_profiles(self):
    #     query = self.session.query(Profile.name)
    #     return [row[0] for row in query.all()]

    # def set_cname(self, urid: str, cname: str):
    #     query = self.session.query(Profile)
    #     profile = query.filter(Profile.urid == urid).first()
    #     profile.name = cname
    #     self.session.commit()

    # def set_email(self, urid: str, email: str):
    #     query = self.session.query(Identity)
    #     identity = query.filter(Identity.urid == urid).first()
    #     identity.email = email
    #     self.session.commit()
    #
    # def set_token(self, urid: str, token: str):
    #     query = self.session.query(Identity)
    #     identity = query.filter(Identity.urid == urid).first()
    #     identity.token = token
    #     self.session.commit()
    #
    # def get_token(self, urid: str) -> str:
    #     query = self.session.query(Identity)
    #     identity = query.filter(Identity.urid == urid).first()
    #     return identity.token

    # def set_user(self, urid: str, token: str, cname: str):
    #     if not self.has_profile(urid):
    #         self.create_profile()
    #     self.set_token(urid, token)
    #     self.set_cname(urid, cname)
    #
    # def get_user(self, urid: str):
    #     query = self.session.query(Identity)
    #     identity = query.filter(Identity.urid == urid).first()
    #     return identity
