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


class PrincipalType(enum.Enum):
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
    principal_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=True, index=True)
    # The type of the principal_id (PROFILE, GROUP, PUBLIC)
    principal_type = sqlalchemy.Column(
        sqlalchemy.Enum(PrincipalType), nullable=False, index=True
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


@sqlalchemy.event.listens_for(sqlalchemy.engine.Engine, "connect")
def create_trigger(dbapi_connection, _connection_record):
    """Create a trigger to enforce the principal_id + principal_type foreign key constraint.
    - Regular foreign key constraints don't work for this case since the principal_id can
    reference either the profile, group table or neither, depending on the principal_type.
    - Regular check constraints also don't work for this case since they can't reference
    other tables (and subqueries can't be used in check constraints).
    """
    cursor = dbapi_connection.cursor()
    cursor.execute(
        """
        create or replace function enforce_principal_id_check()
        returns trigger as $$
        begin
            if
                (new.principal_type = 'PROFILE'::principal_type and not exists
                (select 1 from profile where id = new.principal_id)) or
                (new.principal_type = 'GROUP'::principal_type and not exists
                (select 1 from "group" where id = new.principal_id)) or
                (new.principal_type = 'PUBLIC'::principal_type and new.principal_id is not null)
            then
                raise exception using message = 'invalid principal_type and/or principal_id: ' 
                || new.principal_type || ', ' || new.principal_id;
            end if;
            return new;
        end;
        $$ language plpgsql;

        create or replace trigger principal_id_check_trigger
        before insert or update on permission
        for each row execute function enforce_principal_id_check();
    """
    )
    cursor.close()
