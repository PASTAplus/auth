import daiquiri
import sqlalchemy.orm
import sqlalchemy.pool

import db.base
import db.permission
import util.avatar

log = daiquiri.getLogger(__name__)


class Profile(db.base.Base):
    __tablename__ = 'profile'
    # At the DB level, we use an 'id' integer primary key for rows, and for foreign key
    # relationships.
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The PASTA ID for the user. This is the primary key for the user in our system. We
    # don't use it as a primary key in the DB, however, since it's a string, and string
    # indexes are less efficient than integer indexes.
    pasta_id = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    # The user's given and family names. Initially set to the values provided by the
    # IdP.
    given_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    family_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The email address that the user has chosen as their contact email. Initially set
    # to the email address provided by the IdP.
    email = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # Permit notifications to be sent to this email address.
    email_notifications = sqlalchemy.Column(sqlalchemy.Boolean(), nullable=False, default=False)
    # Initially false, then set to true when the user accepts the privacy policy.
    privacy_policy_accepted = sqlalchemy.Column(sqlalchemy.Boolean(), nullable=False, default=False)
    # The date when the user accepted the privacy policy.
    privacy_policy_accepted_date = sqlalchemy.Column(sqlalchemy.DateTime(), nullable=True)
    organization = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    association = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    has_avatar = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)

    # cascade_backrefs=False:
    # https://sqlalche.me/e/14/s9r1
    # https://sqlalche.me/e/b8d9
    identities = sqlalchemy.orm.relationship(
        'Identity',
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
    # permissions = sqlalchemy.orm.relationship(
    #     'Rule',
    #     back_populates='profile',
    #     cascade_backrefs=False,
    #     cascade='all, delete-orphan',
    # )

    @property
    def full_name(self):
        if self.family_name is None:
            return self.given_name
        return f'{self.given_name} {self.family_name}'

    @full_name.setter
    def full_name(self, full_name):
        try:
            self.given_name, self.family_name = full_name.split(' ', 1)
        except ValueError:
            self.given_name, self.family_name = full_name, None

    @property
    def initials(self):
        return ''.join(s[0].upper() for s in self.full_name.split())

    @property
    def avatar_url(self):
        return str(util.avatar.get_profile_avatar_url(self))
