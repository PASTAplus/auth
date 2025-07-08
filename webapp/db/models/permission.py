import datetime
import enum

import daiquiri
import sqlalchemy.orm

import db.models.base

log = daiquiri.getLogger(__name__)


#
# Tables for tracking resources and permissions.
#


class Resource(db.models.base.Base):
    """A resource is anything for which permissions can be tracked individually.

    Resources can be addressed directly by their key. They also form a tree structure (acyclic
    graph), as each resource can itself be a parent of other resources.

    Multiple resources can have both the same label and type. When searching for a resource,
    any ambiguity is resolved by filtering on permissions on the resource.
    """

    __tablename__ = 'resource'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # Nodes in the resource tree can be either a parent or a child of other nodes.
    # The parent of this resource. If this is null, this resource is a root node.
    parent_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('resource.id'), nullable=True, index=True
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
    rules = sqlalchemy.orm.relationship(
        'Rule',
        back_populates='resource',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )
    parent = sqlalchemy.orm.relationship(
        'Resource', remote_side=[id], lazy='select'
    )

class PermissionLevel(enum.Enum):
    NONE = 0
    READ = 1
    WRITE = 2
    CHANGE = 3  # changePermission


PERMISSION_LEVEL_STRING_TO_ENUM_DICT = {
    'none': PermissionLevel.NONE,
    'read': PermissionLevel.READ,
    'write': PermissionLevel.WRITE,
    'changePermission': PermissionLevel.CHANGE,
}


PERMISSION_LEVEL_ENUM_TO_STRING_DICT = {
    PermissionLevel.NONE: 'none',
    PermissionLevel.READ: 'read',
    PermissionLevel.WRITE: 'write',
    PermissionLevel.CHANGE: 'changePermission',
}


def subject_type_string_to_enum(subject_type):
    """Convert a string to a SubjectType enum."""
    return SubjectType[subject_type.upper()]


def permission_level_int_to_enum(permission_level):
    """Convert an integer to a PermissionLevel enum."""
    return PermissionLevel(permission_level)


def permission_level_string_to_enum(permission_level_str):
    """Convert a string to a PermissionLevel enum."""
    try:
        return PERMISSION_LEVEL_STRING_TO_ENUM_DICT[permission_level_str]
    except KeyError:
        raise ValueError(
            f'Permission level must be one of: read, write, or changePermission. '
            f'Received: {permission_level_str}'
        )


def permission_level_enum_to_string(permission_level_enum):
    """Convert a PermissionLevel enum to a string."""
    return PERMISSION_LEVEL_ENUM_TO_STRING_DICT[permission_level_enum]


def get_permission_level_enum(permission_level):
    """This is a workaround for a bug in SQLAlchemy, psycopg or Postgres that can cause ENUM type
    columns to be returned as strings instead of enum objects. If `permission_level` already is a
    PermissionLevel ENUM, it is returned unchanged. If it is a string, it is converted to the
    corresponding ENUM.

    TODO: Later in 2025, check if this is still needed.

    Specifically, this happens for me only on the last row of a query result. It's not caused by
    the data in the row itself, as it happens regardless of which row is the last row. Current
    versions are:

    - sqlalchemy=2.0.41=py311h9ecbd09_0
    - psycopg=3.2.9=pyhd5ab78c_0
    - psycopg-c=3.2.9=py311hafcc203_0
    - PostgreSQL 14.17 (Ubuntu 14.17-0ubuntu0.22.04.1)

    To reproduce the bug:

    rows = (
        await populated_dbi.session.execute(sqlalchemy.select(Rule))
    ).scalars().all()
    for row in rows:
        # With bug still present, the permission level on the last row will be a string here.
        # On the rest of the rows, it's the expected enum.
    """
    p = permission_level
    return p if isinstance(p, PermissionLevel) else PermissionLevel[p]


def get_subject_type_enum(subject_type):
    """Like get_permission_level_enum()"""
    s = subject_type
    return s if isinstance(s, SubjectType) else SubjectType[s]


class SubjectType(enum.Enum):
    PROFILE = 1
    GROUP = 2


class Rule(db.models.base.Base):
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
    permission = sqlalchemy.Column(sqlalchemy.Enum(PermissionLevel), nullable=False, default=1)
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


class Principal(db.models.base.Base):
    """A principal maps a principal identifier to a user profile or user group."""

    __tablename__ = 'principal'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The user profile or user group represented by this principal.
    subject_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, index=True)
    # The type of the entity (enum of PROFILE or GROUP).
    subject_type = sqlalchemy.Column(sqlalchemy.Enum(SubjectType), nullable=False, index=True)
    __table_args__ = (
        sqlalchemy.UniqueConstraint('subject_id', 'subject_type', name='subject_id_type_unique'),
    )
    rules = sqlalchemy.orm.relationship(
        'Rule',
        back_populates='principal',
        # cascade_backrefs=False,
        # cascade='all, delete-orphan',
    )
