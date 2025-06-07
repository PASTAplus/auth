import datetime

import daiquiri
import sqlalchemy.orm
import sqlalchemy.pool

import db.models.base
import util.avatar

log = daiquiri.getLogger(__name__)


class Profile(db.models.base.Base):
    """Currently active user profiles."""

    __tablename__ = 'profile'
    # At the DB level, we use an 'id' integer primary key for rows, and for foreign key
    # relationships.
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The EDI-ID for the user. This is the primary key for the user in our system. We
    # don't use it as a primary key in the DB, however, since it's a string, and string
    # indexes are less efficient than integer indexes.
    edi_id = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    # The user's common (full) name. This is typically given name and family name when using Western
    # naming conventions, but any string is accepted.
    common_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The email address that the user has chosen as their contact email. Initially set
    # to the email address provided by the IdP.
    email = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # Permit notifications to be sent to this email address.
    email_notifications = sqlalchemy.Column(sqlalchemy.Boolean(), nullable=False, default=False)
    # Initially false, then set to true when the user accepts the privacy policy.
    privacy_policy_accepted = sqlalchemy.Column(sqlalchemy.Boolean(), nullable=False, default=False)
    # The date when the user accepted the privacy policy.
    privacy_policy_accepted_date = sqlalchemy.Column(sqlalchemy.DateTime(), nullable=True)
    has_avatar = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)

    # cascade_backrefs=False:
    # https://sqlalche.me/e/14/s9r1
    # https://sqlalche.me/e/b8d9
    identities = sqlalchemy.orm.relationship(
        # The name of the class to which this relationship refers.
        'Identity',
        # The name of the attribute on the related class that refers back to this relationship. This
        # can be skipped if a two-way relationship is not needed.
        back_populates='profile',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )
    groups = sqlalchemy.orm.relationship(
        'Group',
        back_populates='profile',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )
    group_members = sqlalchemy.orm.relationship(
        'GroupMember',
        back_populates='profile',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )
    # One-way relationship to the db.models.permission.Principal table.
    principal = sqlalchemy.orm.relationship(
        'db.models.permission.Principal',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
        foreign_keys='db.models.permission.Principal.subject_id',
        primaryjoin=(
            "and_(db.models.permission.Principal.subject_id == db.models.profile.Profile.id, db.models.permission.Principal.subject_type == 'PROFILE')"
        ),
    )

    @property
    def initials(self):
        return ''.join(s[0].upper() for s in self.common_name.split())

    @property
    def avatar_url(self):
        return str(util.avatar.get_profile_avatar_url(self))


class ProfileHistory(db.models.base.Base):
    """History of merged user profiles."""

    __tablename__ = 'profile_history'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # Reference the user's current profile
    profile_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('profile.id'), nullable=False, index=True
    )
    # EDI-ID of a profile that has been merged by the user referenced by profile_id.
    edi_id = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
