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
    # E.g., for package entities: 'quality_report', 'metadata', 'data'
    type = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    # resource_id
    created_date = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    __table_args__ = (
        sqlalchemy.CheckConstraint(
            "type IN ('quality_report', 'metadata', 'data', 'package')",
            name='resource_type_check',
        ),
    )
    collection = sqlalchemy.orm.relationship(
        'Collection',
        back_populates='resources',
        # cascade_backrefs=False,
        passive_deletes=True,
    )
    permissions = sqlalchemy.orm.relationship(
        'Permission',
        back_populates='resource',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )


class PermissionLevel(enum.Enum):
    READ = 1
    WRITE = 2
    OWN = 3


class GranteeType(enum.Enum):
    PROFILE = 1
    GROUP = 2
    PUBLIC = 3


class Permission(db.base.Base):
    __tablename__ = 'permission'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The resource to which this permission applies.
    resource_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('resource.id'),
        nullable=False,
        index=True,
    )
    # The profile or group which is granted this permission.
    # When the type is 'pub', the only valid value is 0.
    grantee_id = sqlalchemy.Column(
        sqlalchemy.Integer, nullable=False, index=True
    )
    # The type of the grantee_id (pro=profile, grp=group, pub=public)
    grantee_type = sqlalchemy.Column(
        sqlalchemy.Enum(GranteeType), nullable=False, index=True
    )
    # The date and time this permission was granted.
    granted_date = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    # The permission level (1=Reader, 2=Writer, 3=Owner)
    level = sqlalchemy.Column(
        sqlalchemy.Enum(PermissionLevel), nullable=False, default=1
    )
    __table_args__ = (
        sqlalchemy.UniqueConstraint(
            'resource_id', 'grantee_id', 'grantee_type', name='resource_profile_unique'
        ),
        # sqlalchemy.exc.NotSupportedError: (psycopg2.errors.FeatureNotSupported) cannot use
        # subquery in check constraint
        #
        # sqlalchemy.CheckConstraint(
        #     """
        #     (type = 'PROFILE' AND grantee_id IN (SELECT id FROM profile)) OR
        #     (type = 'GROUP' AND grantee_id IN (SELECT id FROM "group")) OR
        #     (type = 'PUBLIC' AND grantee_id = 0)
        #     """,
        #     name='grantee_id_check',
        # ),
    )
    resource = sqlalchemy.orm.relationship(
        'Resource',
        back_populates='permissions',
        # cascade_backrefs=False,
        passive_deletes=True,
    )
