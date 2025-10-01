import datetime

import daiquiri
import sqlalchemy.orm
import sqlalchemy.pool

import db.models.base

log = daiquiri.getLogger(__name__)


class Group(db.models.base.Base):
    __tablename__ = 'group'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The group EDI-ID. This is the unique reference for the group in PASTA.
    edi_id = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True, index=True)
    # The profile of the user who create the group.
    profile_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('profile.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    # The name of the group as provided by the user. Can be edited.
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    # The description of the group as provided by the user. Can be edited.
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The date and time the group was created.
    created = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now)
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
        passive_deletes=True,
    )

    profile = sqlalchemy.orm.relationship(
        'db.models.profile.Profile',
        back_populates='groups',
        cascade_backrefs=False,
        passive_deletes=True,
    )

    # rules = sqlalchemy.orm.relationship('Rule', back_populates='resource')

    # @sqlalchemy.ext.hybrid.hybrid_property
    # def member_count(self):
    #     return len(self.members)
    #
    # # noinspection PyMethodParameters
    # @member_count.expression
    # def member_count(cls):
    #     return (
    #         sqlalchemy.select(sqlalchemy.func.count(GroupMember.id))
    #         .where(GroupMember.group_id == cls.id)
    #         .label('member_count')
    #     )


class GroupMember(db.models.base.Base):
    __tablename__ = 'group_member'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The group to which the member belongs.
    group_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('group.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    # The profile of the user who is a member of the group. May include the owner of the group.
    # Groups cannot be group members, so we use profile_id instead of principal_id.
    profile_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('profile.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    # The date and time the user was added to the group.
    added = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now)
    group = sqlalchemy.orm.relationship(
        'Group',
        back_populates='members',
        cascade_backrefs=False,
        passive_deletes=True,
    )
    profile = sqlalchemy.orm.relationship(
        'db.models.profile.Profile',
        back_populates='group_members',
        cascade_backrefs=False,
        passive_deletes=True,
    )
    __table_args__ = (
        # Ensure that group_id and profile_id are unique together.
        sqlalchemy.UniqueConstraint('group_id', 'profile_id', name='group_id_profile_id_unique'),
    )
