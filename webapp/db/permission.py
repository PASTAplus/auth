import datetime
import enum

import daiquiri
import sqlalchemy.orm
import sqlalchemy.pool

import db.base

log = daiquiri.getLogger(__name__)


#
# Tables
#


class Collection(db.base.Base):
    __tablename__ = 'collection'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # A label to display and search for the collection
    # E.g., 'edi.39.3'
    label = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    # A type to categorize the collection
    # E.g., 'package'
    type = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    # The date and time the collection was created.
    created_date = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    __table_args__ = (
        # Ensure that scope, identifier and revision are unique together.
        sqlalchemy.UniqueConstraint(
            'label', 'type', name='collection_label_type_unique'
        ),
    )
    resources = sqlalchemy.orm.relationship(
        'Resource',
        back_populates='collection',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )


class Resource(db.base.Base):
    __tablename__ = 'resource'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The collection to which this resource belongs.
    collection_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('collection.id'), nullable=True
    )
    # The type of the resource
    # E.g., for entities: 'quality_report', 'metadata', 'data'
    type = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    # resource_id
    # The PASTA URL of the resource
    # E.g., http://localhost:8088/package/metadata/eml/edi/39/3
    resource_id = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    created_date = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    __table_args__ = (
        sqlalchemy.CheckConstraint(
            "type IN ('quality_report', 'metadata', 'data')",
            name='resource_type_check',
        ),
    )
    collection = sqlalchemy.orm.relationship(
        'Collection',
        back_populates='resources',
        # cascade_backrefs=False,
        passive_deletes=True,
    )


class PermissionLevel(enum.Enum):
    READ = 1
    WRITE = 2
    CHANGE = 3


class Permission(db.base.Base):
    __tablename__ = 'permission'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The resource to which this permission applies.
    resource_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('permission.id'), nullable=True
    )
    # The profile of the user who is granted this permission.
    profile_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('profile.id'), nullable=False
    )
    # The date and time this permission was granted.
    granted_date = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    # The permission level
    permission_level = sqlalchemy.Column(
        sqlalchemy.Enum(PermissionLevel), nullable=False
    )
