import datetime
import enum

import daiquiri
import sqlalchemy.orm

import db.base

log = daiquiri.getLogger(__name__)


#
# Tables for tracking permissions on resources.
#


class Collection(db.base.Base):
    """A collection of resources.

    Multiple collections can have both the same label and type. Which collection a resource belongs
    to is determined by the resource's collection_id. When searching for a collection, any ambiguity
    is resolved by filtering on permissions on the referencing resource.
    """

    __tablename__ = 'collection'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # A human-readable name to display for the collection.
    # E.g., 'edi.39.3'
    label = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    # A string that describes the type of the collection.
    # E.g., 'package'
    type = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    # The date and time the collection was created.
    created_date = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    resources = sqlalchemy.orm.relationship(
        'Resource',
        back_populates='collection',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )


class Resource(db.base.Base):
    """A resource is anything for which permissions can be tracked individually.

    The resource key is the unique identifier for the resource.

    Multiple resources can have both the same label and type. When searching for a resource,
    any ambiguity is resolved by filtering on permissions on the resource.
    """

    __tablename__ = 'resource'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The collection to which this resource belongs. For a standalone resource, this is null.
    collection_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('collection.id'), nullable=True, index=True
    )
    # The unique identifier for the resource.
    # E.g., for packages and entities objects, The PASTA URL of the resource
    # http://localhost:8088/package/metadata/eml/edi/39/3
    key = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True, unique=True)
    # A human-readable name to display for the resource
    label = sqlalchemy.Column(sqlalchemy.String, nullable=True, index=True)
    # A string that describes the type of the resource.
    # This string is used for grouping resources of the same type.
    # E.g., for package entities: 'data', 'metadata'
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
    NONE = 0
    READ = 1
    WRITE = 2
    CHANGE = 3  # changePermission


class EntityType(enum.Enum):
    PROFILE = 1
    GROUP = 2


class Rule(db.base.Base):
    """A rule is a permission granted to a principal (user profile or user group) on a resource."""

    __tablename__ = 'rule'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The resource to which this permission applies.
    resource_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('resource.id'), nullable=False, index=True
    )
    # The principal (user profile or user group) to which the permission is granted.
    # principal_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, index=True)
    principal_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('principal.id'), nullable=False, index=True
    )
    # The access level granted by this permission (enum of READ, WRITE or CHANGE).
    level = sqlalchemy.Column(sqlalchemy.Enum(PermissionLevel), nullable=False, default=1)
    # The date and time this permission was granted.
    granted_date = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    __table_args__ = (
        sqlalchemy.UniqueConstraint('resource_id', 'principal_id', name='resource_profile_unique'),
    )
    resource = sqlalchemy.orm.relationship(
        'Resource',
        back_populates='rules',
        # cascade_backrefs=False,
        passive_deletes=True,
    )
    principal = sqlalchemy.orm.relationship(
        'Principal',
        back_populates='rules',
        # cascade_backrefs=False,
        # delete-orphan cascade is normally configured only on the "one" side of a one-to-many relationship
        # cascade='all, delete-orphan',
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

