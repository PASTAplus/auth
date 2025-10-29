import datetime

import daiquiri
import sqlalchemy.orm
import sqlalchemy.pool

import db.models.base

log = daiquiri.getLogger(__name__)


class Key(db.models.base.Base):
    __tablename__ = 'key'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The profile of the user who created and owns the key.
    profile_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('profile.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    # The group that this key provides access to. When null, the key provides read-write access
    # to the user profile of the key owner, as referenced by profile_id.
    group_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('group.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    # SHA-256 hash of the key secret.
    secret_hash = sqlalchemy.Column(
        sqlalchemy.LargeBinary(32), nullable=False, unique=True, index=True
    )
    # A short preview of the key secret to help users identify the key.
    secret_preview = sqlalchemy.Column(
        sqlalchemy.String(5), nullable=False, unique=False, index=False
    )
    # The name of the key as provided by the user. Can be edited.
    name = sqlalchemy.Column(sqlalchemy.String(64), nullable=False)
    # The number of times the key has been used for generating a token.
    use_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    # Date-times
    valid_from = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    valid_to = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    created = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now)
    updated = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
    last_used = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    profile = sqlalchemy.orm.relationship(
        'db.models.profile.Profile',
        back_populates='keys',
        cascade_backrefs=False,
        passive_deletes=True,
    )
    group = sqlalchemy.orm.relationship(
        'db.models.group.Group',
        back_populates='keys',
        cascade_backrefs=False,
        passive_deletes=True,
    )
