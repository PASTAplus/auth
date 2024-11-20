import datetime

import daiquiri
import sqlalchemy.ext.hybrid
import sqlalchemy.orm
import sqlalchemy.pool

import db.base

log = daiquiri.getLogger(__name__)


#
# Tables
#


class Group(db.base.Base):
    __tablename__ = 'group'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # Our 'Group Random ID' (GRID) for the group. This is the primary key for the group
    # in our system.
    grid = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    # The profile of the user who created and owns the group.
    profile_id = sqlalchemy.Column(
        sqlalchemy.String, sqlalchemy.ForeignKey('profile.id'), nullable=False
    )
    # The name of the group as provided by the user. Can be edited.
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    # The description of the group as provided by the user. Can be edited.
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The date and time the group was created.
    created = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    # The date and time the group was last updated.
    updated = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
    # The date and time the group was deleted. If this is not null, the group is
    # considered deleted.
    deleted = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)

    members = sqlalchemy.orm.relationship(
        'GroupMember',
        back_populates='group',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )
    profile = sqlalchemy.orm.relationship(
        'Profile',
        back_populates='groups',
        cascade_backrefs=False,
    )

    @sqlalchemy.ext.hybrid.hybrid_property
    def member_count(self):
        return len(self.members)

    @member_count.expression
    def member_count(cls):
        return (
            sqlalchemy.select([sqlalchemy.func.count(GroupMember.id)])
            .where(GroupMember.group_id == cls.id)
            .label('member_count')
        )


class GroupMember(db.base.Base):
    __tablename__ = 'group_member'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The GRID of the group to which the member belongs.
    group_id = sqlalchemy.Column(
        sqlalchemy.String, sqlalchemy.ForeignKey('group.id'), nullable=False
    )
    # The profile of the user who is a member of the group. Does not include the owner
    # of the group.
    profile_id = sqlalchemy.Column(
        sqlalchemy.String, sqlalchemy.ForeignKey('profile.id'), nullable=False
    )
    # The date and time the user was added to the group.
    added = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )

    group = sqlalchemy.orm.relationship(
        'Group',
        back_populates='members',
        cascade_backrefs=False,
    )
    profile = sqlalchemy.orm.relationship(
        'Profile',
        back_populates='group_members',
        cascade_backrefs=False,
    )

    __table_args__ = (
        # Ensure that group_id and profile_id are unique together.
        sqlalchemy.UniqueConstraint(
            'group_id', 'profile_id', name='group_id_profile_id_unique'
        ),
    )
