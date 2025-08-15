import datetime
import enum

import daiquiri
import sqlalchemy.orm
import sqlalchemy.pool

import db.models.base

log = daiquiri.getLogger(__name__)


class IdpName(enum.Enum):
    """The Identity Provider (IdP) names are used to identify the source of the identity."""

    # The UNKNOWN IdP is used for identities created via the API, where the IdP is not known.
    UNKNOWN = 0
    LDAP = 1
    GITHUB = 2
    GOOGLE = 3
    MICROSOFT = 4
    ORCID = 5


IDP_NAME_ENUM_TO_DISPLAY_DICT = {
    IdpName.UNKNOWN: 'Unknown',
    IdpName.GITHUB: 'GitHub',
    IdpName.GOOGLE: 'Google',
    IdpName.LDAP: 'LDAP',
    IdpName.MICROSOFT: 'Microsoft',
    IdpName.ORCID: 'ORCID',
}


def idp_name_enum_to_display(idp_name: IdpName) -> str:
    """Convert an IdPName enum to a display string."""
    try:
        return IDP_NAME_ENUM_TO_DISPLAY_DICT[idp_name]
    except KeyError:
        raise ValueError(f'Unknown IdPName enum value: {idp_name}') from None


class Identity(db.models.base.Base):
    __tablename__ = 'identity'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # Identities have a many-to-one relationship with Profiles. This allows us to find the one
    # Profile that corresponds to a given Identity, and to find all Identities that correspond to a
    # given Profile. The latter is referenced via the backref 'identities' in the Profile. The
    # 'profile_id' declaration creates the physical column in the table which tracks the
    # relationship. Setting 'profile_id' nullable to False forces the identity to be linked to an
    # existing profile. The 'profile' declaration specifies the relationship for use only in the ORM
    # layer.
    profile_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('profile.id'), nullable=False, index=True
    )
    # Our name for the IdP. This acts as a namespace for the subject (sub) provided by the IdP.
    idp_name = sqlalchemy.Column(sqlalchemy.Enum(IdpName), nullable=True, index=True)
    # The idp_uid is the unique user ID provided by the IdP, not to be confused with the UID that is
    # part of a LDAP DN, which we usually reference as `dn_uid`. The source of this value varies
    # with the IdP. E.g., for Google, it's the 'sub' (subject) and for ORCID, it's an ORCID on URL
    # form. The value is unique within the IdP's namespace. It is only guaranteed to be unique
    # within our system when combined with the idp_name.
    idp_uid = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    # The user's common (full) name provided by the IdP. This is typically given name and family
    # name when using Western naming conventions, but any string is accepted. This value can change
    # if the user updates their profile with the IdP. It will be null if the user has not yet
    # signed in.
    common_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The email address provided by the IdP. This will change if the user updates their email
    # address with the IdP.
    email = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The date and time of the first successful authentication with this identity.
    first_auth = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    # The date and time of the most recent successful authentication with this identity.
    last_auth = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    # True if an avatar has been successfully downloaded and stored in the file system
    # for this IdP.
    has_avatar = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)

    profile = sqlalchemy.orm.relationship(
        'db.models.profile.Profile',
        back_populates='identities',
        cascade_backrefs=False,
    )
    __table_args__ = (
        # Ensure that idp_name and idp_uid are unique together (each IdP has its own namespace for
        # unique identifiers)
        sqlalchemy.UniqueConstraint('idp_name', 'idp_uid', name='idp_name_uid_unique'),
    )
