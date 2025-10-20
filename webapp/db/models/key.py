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
    # The key ID. This is the unique external reference for the key.
    key_id = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True, index=True)
    # The description of the key as provided by the user. Can be edited.
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # Dates
    valid_from = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    valid_to = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    created = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now)
    updated = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
    profile = sqlalchemy.orm.relationship(
        'db.models.profile.Profile',
        back_populates='keys',
        cascade_backrefs=False,
        passive_deletes=True,
    )
