import datetime

import daiquiri
import sqlalchemy.pool

import db.base

log = daiquiri.getLogger(__name__)


class Sync(db.base.Base):
    """Track table changes for synchronization with in-memory caches."""

    __tablename__ = 'sync'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True, index=True)
    updated = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
