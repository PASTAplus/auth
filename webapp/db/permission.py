import datetime
import enum

import daiquiri
import sqlalchemy.orm
import sqlalchemy.event
import sqlalchemy.engine

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
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('collection.id'),
        nullable=True,
        index=True,
    )
    # For packages and entities objects, The PASTA URL of the resource
    # E.g., http://localhost:8088/package/metadata/eml/edi/39/3
    label = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    # The type of the resource
    # This is a string that is used for grouping resources of the same type.
    # E.g., for package entities: 'quality_report', 'metadata', 'data'
    type = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    created_date = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    collection = sqlalchemy.orm.relationship(
        'Collection',
        back_populates='resources',
        # cascade_backrefs=False,
        passive_deletes=True,
    )
    rules = sqlalchemy.orm.relationship(
        'Rule',
        back_populates='resource',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )


class PermissionLevel(enum.Enum):
    READ = 1
    WRITE = 2
    OWN = 3


class PrincipalType(enum.Enum):
    PROFILE = 1
    GROUP = 2


class Rule(db.base.Base):
    """A rule is a permission granted to a principal (user profile or user group) on a resource."""

    __tablename__ = 'rule'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The resource to which this permission applies.
    resource_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('resource.id'),
        nullable=False,
        index=True,
    )
    # The principal (user profile or user group) to which the permission is granted.
    # principal_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, index=True)
    principal_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('principal.id'), nullable=False, index=True
    )
    # The date and time this permission was granted.
    granted_date = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    # The permission level (READ, WRITE, OWN)
    level = sqlalchemy.Column(
        sqlalchemy.Enum(PermissionLevel), nullable=False, default=1
    )
    __table_args__ = (
        sqlalchemy.UniqueConstraint(
            'resource_id', 'principal_id', 'principal_type', name='resource_profile_unique'
        ),
    )
    resource = sqlalchemy.orm.relationship(
        'Resource',
        back_populates='permissions',
        # cascade_backrefs=False,
        passive_deletes=True,
    )


class Principal(db.base.Base):
    """A principal maps a principal identifier to a user profile or user group."""

    __tablename__ = 'principal'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The user profile or user group represented by this principal.
    entity_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, index=True)
    # The type of the entity (enum of PROFILE or GROUP).
    entity_type = sqlalchemy.Column(sqlalchemy.Enum(EntityType), nullable=False, index=True)
    __table_args__ = (
        sqlalchemy.UniqueConstraint('entity_id', 'entity_type', name='entity_id_type_unique'),
    )
    rules = sqlalchemy.orm.relationship(
        'Rule',
        back_populates='principal',
        # cascade_backrefs=False,
        # cascade='all, delete-orphan',
    )

