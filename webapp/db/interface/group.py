import datetime

import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

import util.profile_cache
from config import Config
from db.models.group import Group, GroupMember
from db.models.permission import SubjectType, Resource, Rule, PermissionLevel, Principal
import util.edi_id

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class GroupInterface:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    async def create_group(self, token_profile_row, name, description, edi_id=None):
        """Create a new group which will be owned by token_profile_row.

        This also creates a resource to track permissions on the group, and sets CHANGE permission
        for the group owner on the group resource.
        """
        edi_id = edi_id or util.edi_id.get_random_edi_id()
        new_group_row = Group(
            edi_id=edi_id,
            profile=token_profile_row,
            name=name,
            description=description or None,
        )
        self._session.add(new_group_row)
        await self.flush()
        # Create the principal for the group. The principal gives us a single ID, the principal ID,
        # to use when referencing the group in rules for other resources. This principal is not
        # needed when creating the group and associated resource.
        await self._add_principal(new_group_row.id, SubjectType.GROUP)
        # Create a top level resource for tracking permissions on the group. We use the group EDI-ID
        # as the resource key. Since it's impossible to predict what the EDI-ID will be for a new
        # group, it's not possible to create resources that would interfere with groups created
        # later.
        resource_row = await self.create_resource(None, edi_id, name, 'group')
        # Create a permission for the group owner on the group resource.
        principal_row = await self.get_principal_by_subject(
            token_profile_row.id, SubjectType.PROFILE
        )
        await self.create_or_update_rule(
            resource_row,
            principal_row,
            PermissionLevel.CHANGE,
        )
        await self.flush()
        return new_group_row, resource_row

    async def get_vetted_group(self):
        """Get the vetted group."""
        result = await self.execute(
            sqlalchemy.select(Group).where(Group.edi_id == Config.VETTED_GROUP_EDI_ID)
        )
        return result.scalar_one()

    async def get_group(self, group_id):
        """Get a group by its ID."""
        result = await self.execute(sqlalchemy.select(Group).where(Group.id == group_id))
        return result.scalar_one()

    async def get_group_by_edi_id(self, edi_id):
        """Get a group by its EDI-ID."""
        result = await self.execute(sqlalchemy.select(Group).where(Group.edi_id == edi_id))
        return result.scalar_one()

    async def get_owned_group(self, token_profile_row, group_id):
        """Get a group by its ID.
        Raises an exception if token_profile_row does not have WRITE or CHANGE on the group.
        """
        stmt = sqlalchemy.select(Group).where(
            Group.id == group_id,
        )
        if not util.profile_cache.is_superuser(token_profile_row):
            stmt = (
                stmt.join(
                    Resource,
                    Resource.key == Group.edi_id,
                )
                .join(
                    Rule,
                    Rule.resource_id == Resource.id,
                )
                .join(
                    Principal,
                    Principal.id == Rule.principal_id,
                )
                .where(
                    Principal.subject_id == token_profile_row.id,
                    Principal.subject_type == SubjectType.PROFILE,
                    Rule.permission >= PermissionLevel.WRITE,
                )
            )
        result = await self.execute(stmt)
        return result.scalar_one()

    async def get_all_owned_groups(self, token_profile_row):
        """Get the groups on which this profile has WRITE or CHANGE permissions.
        Superuser profiles get all groups.
        """
        stmt = sqlalchemy.select(Group).order_by(
            Group.name,
            Group.description,
            sqlalchemy.asc(Group.created),
            Group.id,
        )
        if not util.profile_cache.is_superuser(token_profile_row):
            stmt = (
                stmt.join(
                    Resource,
                    Resource.key == Group.edi_id,
                )
                .join(
                    Rule,
                    Rule.resource_id == Resource.id,
                )
                .join(
                    Principal,
                    Principal.id == Rule.principal_id,
                )
                .where(
                    Principal.subject_id == token_profile_row.id,
                    Principal.subject_type == SubjectType.PROFILE,
                    Rule.permission >= PermissionLevel.WRITE,
                )
            )
        result = await self.execute(stmt)
        return result.scalars().all()

    async def update_group(self, token_profile_row, group_id, name, description):
        """Update a group by its ID.
        Raises an exception if the group is not owned by the profile.
        """
        group_row = await self.get_owned_group(token_profile_row, group_id)
        group_row.name = name
        group_row.description = description or None
        await self._set_resource_label_by_key(group_row.edi_id, name)

    async def delete_group(self, token_profile_row, group_id):
        """Delete a group by its ID.
        Raises an exception if the group is not owned by the profile.
        """
        group_row = await self.get_owned_group(token_profile_row, group_id)
        # Delete group members
        await self.execute(sqlalchemy.delete(GroupMember).where(GroupMember.group == group_row))
        # Delete the group
        await self._session.delete(group_row)
        # Remove associated resource
        await self._remove_resource_by_key(group_row.edi_id)

    async def add_group_member(self, token_profile_row, group_id, member_profile_id):
        """Add a member to a group.
        Raises an exception if the group is not owned by the profile.
        """
        group_row = await self.get_owned_group(token_profile_row, group_id)
        new_member_row = GroupMember(
            group=group_row,
            profile_id=member_profile_id,
        )
        self._session.add(new_member_row)
        group_row.updated = datetime.datetime.now()

    async def delete_group_member(self, token_profile_row, group_id, member_profile_id):
        """Delete a member from a group.
        Raises an exception if the group is not owned by the profile.
        """
        group_row = await self.get_owned_group(token_profile_row, group_id)
        result = await self.execute(
            sqlalchemy.select(GroupMember).where(
                GroupMember.group == group_row,
                GroupMember.profile_id == member_profile_id,
            )
        )
        member_row = result.scalar_one()
        await self._session.delete(member_row)
        group_row.updated = datetime.datetime.now()

    async def is_vetted(self, token_profile_row):
        """Check if a profile is in the Vetted system group or is a superuser."""
        if util.profile_cache.is_superuser(token_profile_row):
            return True
        return await self.is_in_group(token_profile_row, await self.get_vetted_group())

    async def is_in_group(self, profile_row, group_row):
        """Check if a profile is a member of a group."""
        result = await self.execute(
            sqlalchemy.select(
                sqlalchemy.exists().where(
                    GroupMember.group == group_row,
                    GroupMember.profile == profile_row,
                )
            )
        )
        return result.scalar_one()

    async def get_group_member_list(self, token_profile_row, group_id):
        """Get the members of a group. Only profiles can be group members, so group members are
        returned with profile_id instead of principal_id.
        Raises an exception if the group is not owned by the profile.
        """
        group_row = await self.get_owned_group(token_profile_row, group_id)
        result = await self.execute(
            sqlalchemy.select(GroupMember)
            .options(sqlalchemy.orm.selectinload(GroupMember.profile))
            .where(GroupMember.group == group_row)
        )
        return result.scalars().all()

    async def get_group_member_count(self, token_profile_row, group_id):
        """Get the number of members in a group."""
        group_row = await self.get_owned_group(token_profile_row, group_id)
        result = await self.execute(
            sqlalchemy.select(sqlalchemy.func.count(GroupMember.id)).where(
                GroupMember.group == group_row
            )
        )
        return result.scalar_one()

    async def get_group_membership_list(self, token_profile_row):
        """Get the groups that this profile is a member of."""
        result = await self.execute(
            (
                sqlalchemy.select(Group)
                .options(
                    # sqlalchemy.orm.selectinload(db.models.group.GroupMember.group),
                    sqlalchemy.orm.joinedload(Group.profile),
                )
                .join(GroupMember)
                .where(GroupMember.profile_id == token_profile_row.id)
            )
        )
        return result.scalars().all()

    async def get_group_membership_edi_id_set(self, token_profile_row):
        return {group.edi_id for group in await self.get_group_membership_list(token_profile_row)}

    async def leave_group_membership(self, token_profile_row, group_id):
        """Leave a group.
        This removes the token profile from the group. The profile does not have to own the group.
        Raises an exception if the profile is not a member of the group.
        """
        result = await self.execute(
            sqlalchemy.select(GroupMember)
            .options(sqlalchemy.orm.selectinload(GroupMember.group))
            .where(
                GroupMember.group_id == group_id,
                GroupMember.profile_id == token_profile_row.id,
            )
        )
        member_row = result.scalar_one()
        member_row.group.updated = datetime.datetime.now()
        await self._session.delete(member_row)

    async def get_all_groups_generator(self):
        result = await self._session.stream(
            (
                sqlalchemy.select(
                    Group,
                    Principal,
                )
                .join(
                    Principal,
                    sqlalchemy.and_(
                        Principal.subject_id == Group.id,
                        Principal.subject_type == SubjectType.GROUP,
                    ),
                )
                .options(sqlalchemy.orm.joinedload(Group.profile))
                .order_by(
                    Group.name,
                    Group.description,
                    sqlalchemy.asc(Group.created),
                    Group.id,
                )
            )
        )
        async for group_row, principal_row in result.yield_per(Config.DB_YIELD_ROWS):
            yield group_row, principal_row
