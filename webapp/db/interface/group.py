import datetime

import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

import db.interface.util
from db.models.group import Group, GroupMember
from db.models.permission import SubjectType, Resource, Rule, PermissionLevel, Principal

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class GroupInterface:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    async def create_group(self, token_profile_row, group_name, description, edi_id=None):
        """Create a new group which will be owned by token_profile_row.

        This also creates a resource to track permissions on the group, and sets CHANGE permission
        for the group owner on the group resource.
        """
        edi_id = edi_id or db.interface.util.get_new_edi_id()
        new_group_row = Group(
            edi_id=edi_id,
            profile=token_profile_row,
            name=group_name,
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
        resource_row = await self.create_resource(None, edi_id, group_name, 'group')
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

    # async def assert_has_group_ownership(self, token_profile_row, group_row):
    #     """Assert that the given profile owns the group."""
    #     if group_row.profile_id != token_profile_row.id:
    #         raise ValueError(f'Group {group_row.edi_id} is not owned by profile {token_profile_row.edi_id}')

    async def get_group(self, token_profile_row, group_id):
        """Get a group by its ID.
        Raises an exception if token_profile_row does not have WRITE or CHANGE on the group.
        """
        result = await self.execute(
            (
                sqlalchemy.select(Group)
                .join(
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
                    Group.id == group_id,
                    Principal.subject_id == token_profile_row.id,
                    Principal.subject_type == SubjectType.PROFILE,
                    Rule.permission >= PermissionLevel.WRITE,
                )
            )
        )
        group_row = result.scalar()
        if group_row is None:
            raise ValueError(f'Group {group_id} not found')
        return group_row

    async def update_group(self, token_profile_row, group_id, name, description):
        """Update a group by its ID.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the token profile.
        group_row = await self.get_group(token_profile_row, group_id)
        group_row.name = name
        group_row.description = description or None
        await self._set_resource_label_by_key(group_row.edi_id, name)

    async def delete_group(self, token_profile_row, group_id):
        """Delete a group by its ID.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the token profile.
        group_row = await self.get_group(token_profile_row, group_id)
        # Delete group members
        await self.execute(sqlalchemy.delete(GroupMember).where(GroupMember.group == group_row))
        # Delete the group
        await self._session.delete(group_row)
        # Remove associated resource
        await self._remove_resource_by_key(group_row.edi_id)

    async def add_group_member(self, token_profile_row, group_id, member_profile_id):
        """Add a member to a group.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the profile
        group_row = await self.get_group(token_profile_row, group_id)
        new_member_row = GroupMember(
            group=group_row,
            profile_id=member_profile_id,
        )
        self._session.add(new_member_row)
        group_row.updated = datetime.datetime.now()

    async def delete_group_member(self, token_profile_row, group_id, member_profile_id):
        """Delete a member from a group.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the token profile.
        group_row = await self.get_group(token_profile_row, group_id)
        result = await self.execute(
            sqlalchemy.select(GroupMember).where(
                GroupMember.group == group_row,
                GroupMember.profile_id == member_profile_id,
            )
        )
        member_row = result.scalar()
        if member_row is None:
            raise ValueError(f'Member {member_profile_id} not found in group {group_id}')
        await self._session.delete(member_row)
        group_row.updated = datetime.datetime.now()

    async def get_group_member_list(self, token_profile_row, group_id):
        """Get the members of a group. Only profiles can be group members, so group members are
        returned with profile_id instead of principal_id.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the token profile.
        group_row = await self.get_group(token_profile_row, group_id)
        result = await self.execute(
            sqlalchemy.select(GroupMember)
            .options(sqlalchemy.orm.selectinload(GroupMember.profile))
            .where(GroupMember.group == group_row)
        )
        return result.scalars().all()

    async def get_group_member_count(self, token_profile_row, group_id):
        """Get the number of members in a group.
        TODO: Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the token profile.
        group_row = await self.get_group(token_profile_row, group_id)
        result = await self.execute(
            sqlalchemy.select(sqlalchemy.func.count(GroupMember.id)).where(
                GroupMember.group == group_row
            )
        )
        return result.scalar_one_or_none() or 0

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
        Raises ValueError if the member who is leaving does not match the profile.

        Note: While this method ultimately performs the same action as delete_group_member,
        it performs different checks.
        """
        result = await self.execute(
            sqlalchemy.select(GroupMember)
            .options(sqlalchemy.orm.selectinload(GroupMember.group))
            .where(
                GroupMember.group_id == group_id,
                GroupMember.profile_id == token_profile_row.id,
            )
        )
        member_row = result.scalar()
        if member_row is None:
            raise ValueError(f'Member {token_profile_row.id} not found in group {group_id}')
        member_row.group.updated = datetime.datetime.now()
        await self._session.delete(member_row)

    async def get_all_groups_generator(self):
        result = await self._session.stream(
            (
                sqlalchemy.select(Group)
                .options(sqlalchemy.orm.joinedload(Group.profile))
                .order_by(
                    Group.name,
                    Group.description,
                    sqlalchemy.asc(Group.created),
                    Group.id,
                )
            )
        )
        async for group_row in result.scalars():
            yield group_row

    async def get_owned_groups(self, token_profile_row):
        """Get the groups on which this profile has WRITE or CHANGE permissions."""
        result = await self.execute(
            (
                sqlalchemy.select(Group)
                .join(
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
                .order_by(
                    Group.name,
                    Group.description,
                    sqlalchemy.asc(Group.created),
                    Group.id,
                )
            )
        )
        return result.scalars().all()
