import datetime
import datetime
import enum

import daiquiri
import sqlalchemy.orm
import sqlalchemy.pool

import db.models.base
import db.models.base
import util.avatar

log = daiquiri.getLogger(__name__)


class IdpName(enum.Enum):
    """The Identity Provider (IdP) names are used to identify the source of the identity provider
    account associated with the profile.
    """

    # The SYSTEM IdP is used for system accounts that are not associated with a real user.
    SYSTEM = 0
    # The SKELETON IdP is used for user profiles created via the API, where the IdP is not known.
    SKELETON = 1
    # The remaining IdP names are for real IdPs that users have authenticated with.
    LDAP = 2
    GITHUB = 3
    GOOGLE = 4
    MICROSOFT = 5
    ORCID = 6


IDP_NAME_ENUM_TO_DISPLAY_DICT = {
    IdpName.SYSTEM: 'System',
    IdpName.SKELETON: 'Automatically generated',
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


class Profile(db.models.base.Base):
    """User profiles"""

    __tablename__ = 'profile'
    # Ensure that idp_name and idp_uid are unique together (each IdP has its own namespace for
    # unique identifiers)
    __table_args__ = (
        # Ensure that idp_name and idp_uid are unique together (each IdP has its own namespace for
        # unique identifiers)
        sqlalchemy.UniqueConstraint('idp_name', 'idp_uid', name='idp_name_uid_unique'),
    )
    # At the DB level, we use an 'id' integer primary key for rows, and for foreign key
    # relationships.
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # Our name for the IdP. This acts as a namespace for the subject (sub) provided by the IdP.
    idp_name = sqlalchemy.Column(sqlalchemy.Enum(IdpName), nullable=False, index=True)
    # The idp_uid is the unique user ID provided by the IdP. Can only be NULL if idp_name is
    # SKELETON. Not to be confused with the UID that is part of an LDAP DN, which we usually
    # reference as `dn_uid`. The source of this value varies with the IdP. E.g., for Google, it's
    # the 'sub' (subject) claim and for ORCID, it's the 'orcid' claim on URL form. The value is
    # unique within the IdP's namespace. It is only guaranteed to be unique within our system when
    # combined with the idp_name.
    idp_uid = sqlalchemy.Column(sqlalchemy.String, nullable=True, index=True)
    # The date and time of the first successful authentication. Should only be NULL if idp_name is
    # SKELETON.
    first_auth = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    # The date and time of the most recent successful authentication. Should only be NULL if
    # idp_name is SKELETON.
    last_auth = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    # The EDI-ID for the user. This is the primary key for the user in our system. We don't use it
    # as a primary key in the DB, however, since it's a string, and string indexes are less
    # efficient than integer indexes.
    edi_id = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    # The user's common (full) name. This is typically given name and family name when using Western
    # naming conventions, but any string is accepted. Should only be NULL if idp_name is SKELETON.
    common_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The email address that the user has chosen as their contact email. Initially set to the email
    # address provided by the IdP.
    email = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # Avatar version (ETag / entity tag, or other key), if known. Used to determine if the avatar
    # has changed at the source. If NULL, this profile has no avatar.
    avatar_ver = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # Alternate avatar profile. If set, this profile's avatar is taken from the alternate profile
    # instead of from this profile's avatar fields. This is set if the user has chosen to use the
    # avatar from one of their linked profiles. This should only be set on primary profiles, not on
    # linked profiles, but this is not enforced at the DB level.
    avatar_profile_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('profile.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    # Permit notifications to be sent to this email address.
    email_notifications = sqlalchemy.Column(sqlalchemy.Boolean(), nullable=False, default=False)
    # Initially false, then set to true when the user accepts the privacy policy. We store this flag
    # separately from the date so that we can trigger new acceptance when the privacy policy
    # changes, without losing the date of prior acceptance.
    privacy_policy_accepted = sqlalchemy.Column(sqlalchemy.Boolean(), nullable=False, default=False)
    # The date when the user last accepted the privacy policy.
    privacy_policy_accepted_date = sqlalchemy.Column(sqlalchemy.DateTime(), nullable=True)
    groups = sqlalchemy.orm.relationship(
        'Group',
        back_populates='profile',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
    group_members = sqlalchemy.orm.relationship(
        'GroupMember',
        back_populates='profile',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
    # One-to-one relationship to the db.models.permission.Principal table.
    principal = sqlalchemy.orm.relationship(
        'db.models.permission.Principal',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
        foreign_keys='db.models.permission.Principal.subject_id',
        primaryjoin=(
            "and_("
            "   db.models.permission.Principal.subject_id == db.models.profile.Profile.id, "
            "   db.models.permission.Principal.subject_type == 'PROFILE'"
            ")"
        ),
        uselist=False,
        passive_deletes=True,
    )
    # Resource searches performed by this profile in order to apply permissions.
    search_sessions = sqlalchemy.orm.relationship(
        'SearchSession',
        back_populates='profile',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
        passive_deletes=True,
    )

    @property
    def initials(self):
        if not self.common_name:
            return '?'
        part_tup = self.common_name.split()
        if len(part_tup) > 3:
            part_tup = part_tup[0], part_tup[1], part_tup[-1]
        return ''.join(s[0] for s in part_tup).upper()

    @property
    def avatar_url(self):
        return str(util.avatar.get_profile_avatar_url(self))


class ProfileLink(db.models.base.Base):
    """Link user profiles."""

    __tablename__ = 'profile_link'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The primary profile is the one that the user will be logged into.
    profile_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('profile.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        unique=True,
    )
    # One or more profiles can be linked to the primary profile.
    linked_profile_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('profile.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    link_date = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    __table_args__ = (sqlalchemy.UniqueConstraint('profile_id', 'linked_profile_id'),)
