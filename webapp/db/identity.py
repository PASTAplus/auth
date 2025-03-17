import datetime

import daiquiri
import sqlalchemy.orm
import sqlalchemy.pool

import db.base
import db.permission

log = daiquiri.getLogger(__name__)


class Identity(db.base.Base):
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
        sqlalchemy.Integer, sqlalchemy.ForeignKey('profile.id'), nullable=False, index=True
    )
    # Our name for the IdP. Currently one of 'github', 'google', 'ldap', 'microsoft',
    # 'orcid'.
    # This acts as a namespace for the subject (sub) provided by the IdP.
    idp_name = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    # The idp_uid is the unique user ID provided by the IdP. The source of this value varies
    # with the IdP. E.g., for Google, it's the 'sub' (subject) and for ORCID, it's an
    # ORCID on URL form. The value is unique within the IdP's namespace. It is only
    # unique within our system when combined with the idp_name.
    idp_uid = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    # The email address provided by the IdP. This will change if the user updates their
    # email address with the IdP.
    email = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The date and time of the first successful authentication with this identity.
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
    # True if an avatar has been successfully downloaded and stored in the file system
    # for this IdP.
    has_avatar = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)

    profile = sqlalchemy.orm.relationship(
        'Profile',
        back_populates='identities',
        cascade_backrefs=False,
    )
    __table_args__ = (
        # Ensure that idp_name and idp_uid are unique together (each IdP has its own
        # namespace for unique identifiers)
        sqlalchemy.UniqueConstraint('idp_name', 'idp_uid', name='idp_name_uid_unique'),
        # Ensure that the idp_name is the name of one of our supported IdPs
        sqlalchemy.CheckConstraint(
            "idp_name IN ('github', 'google', 'ldap', 'microsoft', 'orcid')",
            name='idp_name_check',
        ),
    )
