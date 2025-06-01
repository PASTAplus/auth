import datetime
import re
import uuid

import daiquiri
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.pool

import db.base
import db.group
import db.identity
import db.permission
import db.profile
import db.resource_tree
import db.sync
import util.avatar
import util.profile_cache
from config import Config

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class UserDb:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    #
    # Profile and Identity
    #

    async def create_or_update_profile_and_identity(
        self,
        idp_name: str,
        idp_uid: str,
        common_name: str,
        email: str | None,
        has_avatar: bool,
    ) -> db.identity.Identity:
        """Create or update a profile and identity.

        See the table definitions for Profile and Identity for more information on the
        fields.
        """
        identity_row = await self.get_identity(idp_name=idp_name, idp_uid=idp_uid)
        if identity_row is None:
            profile_row = await self.create_profile(
                edi_id=self.get_new_edi_id(),
                common_name=common_name,
                email=email,
                has_avatar=has_avatar,
            )
            identity_row = await self.create_identity(
                profile=profile_row,
                idp_name=idp_name,
                idp_uid=idp_uid,
                common_name=common_name,
                email=email,
                has_avatar=has_avatar,
            )
            # Set the avatar for the profile to the avatar for the identity
            if has_avatar:
                avatar_img = util.avatar.get_avatar_path(idp_name, idp_uid).read_bytes()
                util.avatar.save_avatar(avatar_img, 'profile', profile_row.edi_id)
        else:
            # We do not update the profile if it exists, since the profile belongs to
            # the user, and they may update their profile with their own information.
            await self.update_identity(
                identity_row, idp_name, idp_uid, common_name, email, has_avatar
            )

        # Undo commit()
        # identity_row = await self.get_identity(idp_name=idp_name, idp_uid=idp_uid)

        return identity_row

    #
    # Profile
    #

    async def create_profile(
        self,
        edi_id: str,
        common_name: str = None,
        email: str = None,
        has_avatar: bool = False,
    ):
        new_profile_row = db.profile.Profile(
            edi_id=edi_id,
            common_name=common_name,
            email=email,
            has_avatar=has_avatar,
        )
        self._session.add(new_profile_row)
        await self._session.flush()
        await self._add_principal(new_profile_row.id, db.permission.SubjectType.PROFILE)
        await self.commit()
        return new_profile_row

    async def get_profile(self, edi_id):
        result = await self._session.execute(
            (
                sqlalchemy.select(db.profile.Profile)
                .options(
                    sqlalchemy.orm.selectinload(db.profile.Profile.identities),
                    sqlalchemy.orm.selectinload(db.profile.Profile.principal),
                )
                .where(db.profile.Profile.edi_id == edi_id)
            )
        )
        return result.scalars().first()

    # async def get_profiles_by_ids(self, profile_id_list):
    #     """Get a list of profiles by their IDs.
    #     The list is returned in the order of the IDs in the input list.
    #     """
    #     profile_query = (
    #         await self._session.query(db.profile.Profile)
    #         .filter(db.profile.Profile.id.in_(profile_id_list))
    #         .all()
    #     )
    #     profile_dict = {p.id: p for p in profile_query}
    #     return [
    #         profile_dict[profile_id] for profile_id in profile_id_list if profile_id in profile_dict
    #     ]

    async def update_profile(self, token_profile_row, **kwargs):
        for key, value in kwargs.items():
            setattr(token_profile_row, key, value)
        await self.commit()

    async def delete_profile(self, token_profile_row):
        await self._session.delete(token_profile_row)
        await self.commit()

    async def set_privacy_policy_accepted(self, token_profile_row):
        token_profile_row.privacy_policy_accepted = True
        token_profile_row.privacy_policy_accepted_date = datetime.datetime.now()
        await self.commit()

    # System profiles

    # async def create_authenticated_profile(self):
    #     try:
    #         await self.create_profile(
    #             has_avatar=True,
    #         )
    #     except sqlalchemy.exc.IntegrityError:
    #         # Multiple processes may try to create the authenticated profile at the same time, so we
    #         # handle that here.
    #         await self.rollback()
    #     else:
    #         util.avatar.init_authenticated_avatar()

    async def get_public_profile(self):
        """Get the profile for the public user."""
        return await self.get_profile(Config.PUBLIC_EDI_ID)

    async def get_authenticated_profile(self):
        """Get the profile for the authenticated user."""
        return await self.get_profile(Config.AUTHENTICATED_EDI_ID)

    #
    # Profile History
    #

    async def add_profile_history(
        self,
        token_profile_row,
    ):
        """Add a new profile history entry for the given profile."""
        new_profile_history_row = db.profile.ProfileHistory(
            profile_id=token_profile_row.id,
            edi_id=token_profile_row.edi_id,
            created_date=datetime.datetime.now(),
        )
        self._session.add(new_profile_history_row)
        await self.commit()
        return new_profile_history_row

    async def get_profile_history(self, token_profile_row):
        result = await self._session.execute(
            sqlalchemy.select(db.profile.ProfileHistory).where(
                db.profile.ProfileHistory.id == token_profile_row.id
            )
        )
        return result.scalars().all()

    #
    # Identity
    #

    async def create_identity(
        self,
        profile,
        idp_name: str,
        idp_uid: str,
        common_name: str,
        email: str,
        has_avatar: bool,
    ):
        """Create a new identity for a given profile."""
        new_identity_row = db.identity.Identity(
            profile=profile,
            idp_name=idp_name,
            idp_uid=idp_uid,
            common_name=common_name,
            email=email,
            has_avatar=has_avatar,
        )
        self._session.add(new_identity_row)
        await self.commit()
        return new_identity_row

    async def update_identity(
        self, identity_row, idp_name, idp_uid, common_name, email, has_avatar
    ):
        assert identity_row.idp_name == idp_name
        assert identity_row.idp_uid == idp_uid
        # We always update the email address and common name in the identity row, but only set these
        # in the profile when the profile is first created. So if the user has updated their info
        # with the IdP, the updated info will be stored in the identity, but corresponding info in
        # the profile remains unchanged.
        identity_row.common_name = common_name
        identity_row.email = email
        # Normally, has_avatar will be True from the first time the user logs in with the identity.
        # More rarely, it will go from False to True, if a user did not initially have an avatar at
        # the IdP, but then creates one. More rarely still (if at all possible), this may go from
        # True to False, if the user removes their avatar at the IdP. In this latter case, the
        # avatar image in the filesystem will be orphaned here.
        identity_row.has_avatar = has_avatar
        await self.commit()

    async def get_identity(self, idp_name: str, idp_uid: str):
        result = await self._session.execute(
            (
                sqlalchemy.select(db.identity.Identity)
                .options(sqlalchemy.orm.selectinload(db.identity.Identity.profile))
                .where(
                    db.identity.Identity.idp_name == idp_name,
                    db.identity.Identity.idp_uid == idp_uid,
                )
            )
        )
        return result.scalars().first()

    async def get_identity_by_id(self, identity_id):
        result = await self._session.execute(
            sqlalchemy.select(db.identity.Identity).where(db.identity.Identity.id == identity_id)
        )
        return result.scalars().first()

    async def delete_identity(self, token_profile_row, idp_name: str, idp_uid: str):
        """Delete an identity from a profile."""
        identity_row = await self.get_identity(idp_name, idp_uid)
        if identity_row not in token_profile_row.identities:
            raise ValueError(f'Identity {idp_name} {idp_uid} does not belong to profile')
        await self._session.delete(identity_row)
        await self.commit()

    @staticmethod
    def get_new_edi_id():
        return f'EDI-{uuid.uuid4().hex}'

    async def get_all_profiles(self):
        result = await self._session.execute(
            sqlalchemy.select(db.profile.Profile).order_by(sqlalchemy.asc(db.profile.Profile.id))
        )
        return result.scalars().all()

    async def get_all_profiles_generator(self):
        """Get a generator of all profiles, sorted by name, email, with id as tiebreaker."""
        result = await self._session.stream(
            (
                sqlalchemy.select(db.profile.Profile, db.permission.Principal)
                .join(
                    db.permission.Principal,
                    sqlalchemy.and_(
                        db.permission.Principal.subject_id == db.profile.Profile.id,
                        db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
                    ),
                )
                .order_by(
                    db.profile.Profile.common_name,
                    db.profile.Profile.email,
                    db.profile.Profile.id,
                )
            )
        )
        async for profile_row, principal_row in result:
            yield profile_row, principal_row

    #
    # Group
    #

    async def create_group(self, token_profile_row, group_name, description):
        """Create a new group which will be owned by token_profile_row.

        This also creates a resource to track permissions on the group, and sets CHANGE permission
        for the group owner on the group resource.
        """
        edi_id = UserDb.get_new_edi_id()
        new_group_row = db.group.Group(
            edi_id=edi_id,
            profile=token_profile_row,
            name=group_name,
            description=description or None,
        )
        self._session.add(new_group_row)
        await self._session.flush()
        # Create the principal for the group.
        # The principal gives us a single ID, the principal ID, to use when referencing the group in
        # rules for other resources. This principal is not needed when creating the group and
        # associated resource.
        await self._add_principal(new_group_row.id, db.permission.SubjectType.GROUP)
        # Create a top level resource for tracking permissions on the group. We use the group EDI-ID
        # as the resource key. Since it's impossible to predict what the EDI-ID will be for a new
        # group, it's not possible to create resources that would interfere with groups created
        # later.
        resource_row = await self.create_resource(None, edi_id, group_name, 'group')
        # Create a permission for the group owner on the group resource.
        principal_row = await self.get_principal_by_subject(
            token_profile_row.id, db.permission.SubjectType.PROFILE
        )
        await self._create_or_update_permission(
            resource_row,
            principal_row,
            db.permission.PermissionLevel.CHANGE,
        )
        await self.commit()
        return new_group_row

    # async def assert_has_group_ownership(self, token_profile_row, group_row):
    #     """Assert that the given profile owns the group."""
    #     if group_row.profile_id != token_profile_row.id:
    #         raise ValueError(f'Group {group_row.edi_id} is not owned by profile {token_profile_row.edi_id}')

    async def get_group(self, token_profile_row, group_id):
        """Get a group by its ID.
        Raises an exception if token_profile_row does not have WRITE or CHANGE on the group.
        """
        result = await self._session.execute(
            (
                sqlalchemy.select(db.group.Group)
                .join(
                    db.permission.Resource,
                    db.permission.Resource.key == db.group.Group.edi_id,
                )
                .join(
                    db.permission.Rule,
                    db.permission.Rule.resource_id == db.permission.Resource.id,
                )
                .join(
                    db.permission.Principal,
                    db.permission.Principal.id == db.permission.Rule.principal_id,
                )
                .where(
                    db.group.Group.id == group_id,
                    db.permission.Principal.subject_id == token_profile_row.id,
                    db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
                    db.permission.Rule.permission >= db.permission.PermissionLevel.WRITE,
                )
            )
        )
        group_row = result.scalars().first()
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
        await self.commit()

    async def delete_group(self, token_profile_row, group_id):
        """Delete a group by its ID.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the token profile.
        group_row = await self.get_group(token_profile_row, group_id)
        # Delete group members
        await self._session.execute(
            sqlalchemy.delete(db.group.GroupMember).where(db.group.GroupMember.group == group_row)
        )
        # Delete the group
        await self._session.delete(group_row)
        # Remove associated resource
        await self._remove_resource_by_key(group_row.edi_id)
        await self.commit()

    async def add_group_member(self, token_profile_row, group_id, member_profile_id):
        """Add a member to a group.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the profile
        group_row = await self.get_group(token_profile_row, group_id)
        new_member_row = db.group.GroupMember(
            group=group_row,
            profile_id=member_profile_id,
        )
        self._session.add(new_member_row)
        group_row.updated = datetime.datetime.now()
        await self.commit()

    async def delete_group_member(self, token_profile_row, group_id, member_profile_id):
        """Delete a member from a group.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the token profile.
        group_row = await self.get_group(token_profile_row, group_id)
        result = await self._session.execute(
            sqlalchemy.select(db.group.GroupMember).where(
                db.group.GroupMember.group == group_row,
                db.group.GroupMember.profile_id == member_profile_id,
            )
        )
        member_row = result.scalars().first()
        if member_row is None:
            raise ValueError(f'Member {member_profile_id} not found in group {group_id}')
        await self._session.delete(member_row)
        group_row.updated = datetime.datetime.now()
        await self.commit()

    async def get_group_member_list(self, token_profile_row, group_id):
        """Get the members of a group. Only profiles can be group members, so group members are
        returned with profile_id instead of principal_id.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the token profile.
        group_row = await self.get_group(token_profile_row, group_id)
        result = await self._session.execute(
            sqlalchemy.select(db.group.GroupMember)
            .options(sqlalchemy.orm.selectinload(db.group.GroupMember.profile))
            .where(db.group.GroupMember.group == group_row)
        )
        return result.scalars().all()

    async def get_group_member_count(self, token_profile_row, group_id):
        """Get the number of members in a group.
        TODO: Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the token profile.
        group_row = await self.get_group(token_profile_row, group_id)
        result = await self._session.execute(
            sqlalchemy.select(sqlalchemy.func.count(db.group.GroupMember.id)).where(
                db.group.GroupMember.group == group_row
            )
        )
        return result.scalar_one_or_none() or 0

    async def get_group_membership_list(self, token_profile_row):
        """Get the groups that this profile is a member of."""
        result = await self._session.execute(
            (
                sqlalchemy.select(db.group.Group)
                .join(db.group.GroupMember)
                .where(db.group.GroupMember.profile_id == token_profile_row.id)
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
        result = await self._session.execute(
            sqlalchemy.select(db.group.GroupMember)
            .options(sqlalchemy.orm.selectinload(db.group.GroupMember.group))
            .where(
                db.group.GroupMember.group_id == group_id,
                db.group.GroupMember.profile_id == token_profile_row.id,
            )
        )
        member_row = result.scalars().first()
        if member_row is None:
            raise ValueError(f'Member {token_profile_row.id} not found in group {group_id}')
        member_row.group.updated = datetime.datetime.now()
        await self._session.delete(member_row)
        await self.commit()

    async def get_all_groups_generator(self):
        result = await self._session.stream(
            (
                sqlalchemy.select(db.group.Group)
                .options(sqlalchemy.orm.joinedload(db.group.Group.profile))
                .order_by(
                    db.group.Group.name,
                    db.group.Group.description,
                    sqlalchemy.asc(db.group.Group.created),
                    db.group.Group.id,
                )
            )
        )
        async for group_row in result.scalars():
            yield group_row

    async def get_owned_groups(self, token_profile_row):
        """Get the groups on which this profile has WRITE or CHANGE permissions."""
        result = await self._session.execute(
            (
                sqlalchemy.select(db.group.Group)
                .join(
                    db.permission.Resource,
                    db.permission.Resource.key == db.group.Group.edi_id,
                )
                .join(
                    db.permission.Rule,
                    db.permission.Rule.resource_id == db.permission.Resource.id,
                )
                .join(
                    db.permission.Principal,
                    db.permission.Principal.id == db.permission.Rule.principal_id,
                )
                .where(
                    db.permission.Principal.subject_id == token_profile_row.id,
                    db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
                    db.permission.Rule.permission >= db.permission.PermissionLevel.WRITE,
                )
                .order_by(
                    db.group.Group.name,
                    db.group.Group.description,
                    sqlalchemy.asc(db.group.Group.created),
                    db.group.Group.id,
                )
            )
        )
        return result.scalars().all()

    #
    # Resource and Rule
    #

    async def create_resource(self, parent_id, key, label, type):
        """Create a new resource."""
        new_resource_row = db.permission.Resource(
            parent_id=parent_id,
            key=key,
            label=label,
            type=type,
        )
        self._session.add(new_resource_row)
        await self.commit()
        return new_resource_row

    async def update_resource(
        self, token_profile_row, key, label=None, type=None, parent_resource_row=None
    ):
        """Update a resource.

        The resource must have CHANGE permission for the profile, or a group of which the profile is
        a member.
        """
        resource_row = await self._get_owned_resource_by_key(token_profile_row, key)

        if label:
            resource_row.label = label
        if type:
            resource_row.type = type
        if parent_resource_row:
            result = await self._session.execute(
                sqlalchemy.select(
                    db.resource_tree._get_resource_tree_for_ui(resource_row.id)
                ).where(
                    db.resource_tree._get_resource_tree_for_ui(resource_row.id).id
                    == parent_resource_row.id
                )
            )
            if result.scalars().first():
                raise ValueError(
                    f'Cannot set parent resource: The requested parent is currently a child or '
                    f'descendant of the resource to be updated. resource_id={resource_row.id} '
                    f'parent_resource_id={parent_resource_row.id}'
                )

        await self.commit()

    async def _get_owned_resource_by_key(self, token_profile_row, key):
        """Get a resource by its key. The resource must have CHANGE permission for the profile, or a
        group of which the profile is a member.
        """
        result = await self._session.execute(
            sqlalchemy.select(db.permission.Resource).where(db.permission.Resource.key == key)
        )
        resource_row = result.scalars().first()
        # TODO: Check that the resource is owned by the profile or a group of which the profile is a member.
        if resource_row is None:
            raise ValueError(
                f'Resource not found or not owned by profile. '
                f'key="{key}" EDI-ID="{token_profile_row.edi_id}"'
            )
        return resource_row

    async def _set_resource_label_by_key(self, key, label):
        """Set the label of a resource by its key.
        This, and other methods of this class starting with underscore do not perform their own
        commit.
        """
        result = await self._session.execute(
            sqlalchemy.select(db.permission.Resource).where(db.permission.Resource.key == key)
        )
        resource_row = result.scalars().first()
        if resource_row is None:
            raise ValueError(f'Resource {key} not found')
        resource_row.label = label

    async def _remove_resource_by_key(self, key):
        """Remove a resource by its key.
        This, and other methods of this class starting with underscore do not perform their own
        commit.
        """
        result = await self._session.execute(
            sqlalchemy.select(db.permission.Resource).where(db.permission.Resource.key == key)
        )
        resource_row = result.scalars().first()
        if resource_row is None:
            raise ValueError(f'Resource {key} not found')
        await self._session.delete(resource_row)

    async def get_resource_types(self, token_profile_row):
        """Get a list of resource types that the profile has CHANGE permission on."""
        result = await self._session.execute(
            (
                sqlalchemy.select(db.permission.Resource.type)
                .join(
                    db.permission.Rule,
                    db.permission.Rule.resource_id == db.permission.Resource.id,
                )
                .join(
                    db.permission.Principal,
                    db.permission.Principal.id == db.permission.Rule.principal_id,
                )
                .where(
                    db.permission.Principal.subject_id == token_profile_row.id,
                    db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
                    db.permission.Rule.permission >= db.permission.PermissionLevel.CHANGE,
                )
                .order_by(db.permission.Resource.type)
                .distinct()
            )
        )
        return result.scalars().all()

    async def set_permissions(
        self,
        token_profile_row,
        resource_ids,
        principal_id,
        permission_level,
    ):
        """Securely set the permission level for a principal on a set of resources designated by
        resource IDs.

        Post-conditions:
            - permission_level == 0: No permission rows will exist for the principal on the
            resources in resource_list.
            - permission_level > 0: A permission row for each resource in resource_list, with the
            given principal and permission_level will exist.

        If the token_profile_row does not have CHANGE permission for a resource, the resource will
        be silently ignored and any existing permission rows for that resource will not be changed.

        If a resource does not exist, it will be silently ignored.

        :param token_profile_row: The profile of the user who is updating the permission. The user
        must have authenticated and must be holding a valid token for this profile.
        :param resource_ids: A sequence of resource IDs to grant the permission on.
        :param principal_id: The ID of the principal (profile or group) to grant the permission to.
        :param permission_level: The permission level to grant (READ, WRITE, CHANGE).
        """

        permission_level = db.permission.permission_level_int_to_enum(permission_level)

        parent_id_set = set()

        # Recursively find all parent IDs of the resources in resource_ids.

        async def _find_parent_ids(resource_id):
            """Recursively find all parent IDs of the given resource ID."""
            result = await self._session.execute(
                sqlalchemy.select(db.permission.Resource.parent_id).where(
                    db.permission.Resource.id == resource_id
                )
            )
            parent_id = result.scalar_one_or_none()
            if parent_id is not None:
                parent_id_set.add(parent_id)
                await _find_parent_ids(parent_id)

        for resource_id in resource_ids:
            await _find_parent_ids(resource_id)

        resource_ids = list(set(resource_ids) | parent_id_set)

        log.debug(f'resource_ids: {resource_ids}')
        log.debug(f'parent_id_set: {parent_id_set}')

        # Databases have a limit to the number of parameters they can accept in a single query, so
        # we chunk the list of resource IDs, which then also limits the number of rows we attempt to
        # create or update in a single bulk query.
        for i in range(0, len(resource_ids), Config.DB_CHUNK_SIZE):
            resource_chunk_list = resource_ids[i : i + Config.DB_CHUNK_SIZE]
            # Filter the resource_chunk_list to only include resources for which the
            # token_profile_row has CHANGE permission (which also filters out any non-existing
            # resource IDs).
            # Superusers have permission on all resources, so we do not need to filter.
            if util.profile_cache.is_superuser(token_profile_row):
                change_resource_id_set = set(resource_chunk_list)
            else:
                # Get the resource IDs for which the token_profile_row has CHANGE permission.
                result = await self._session.execute(
                    (
                        sqlalchemy.select(db.permission.Resource.id)
                        .join(
                            db.permission.Rule,
                            db.permission.Rule.resource_id == db.permission.Resource.id,
                        )
                        .join(
                            db.permission.Principal,
                            db.permission.Principal.id == db.permission.Rule.principal_id,
                        )
                        .where(
                            # db.permission.Resource.id.in_(resource_chunk_list),
                            db.permission.Principal.subject_id == token_profile_row.id,
                            db.permission.Principal.subject_type
                            == db.permission.SubjectType.PROFILE,
                            db.permission.Rule.permission >= db.permission.PermissionLevel.CHANGE,
                        )
                    )
                )
                change_resource_id_set = {row for row, in result.all()}

                change_resource_id_set = set(resource_chunk_list)

            log.debug(f'change_resource_id_set: {change_resource_id_set}')
            # If permission is NONE, all we need to do is delete any existing permission rows for
            # the principal on the given resources.
            if permission_level == db.permission.PermissionLevel.NONE:
                delete_stmt = sqlalchemy.delete(db.permission.Rule).where(
                    db.permission.Rule.resource_id.in_(change_resource_id_set),
                    db.permission.Rule.principal_id == principal_id,
                )
                await self._session.execute(delete_stmt)
                await self.commit()
                return
            # Create a set of secure resource IDs for which there are no existing permission rows
            # for the principal.
            # We start by creating a subquery which returns the resource IDs for which the principal
            # already has a permission row.
            result = await self._session.execute(
                sqlalchemy.select(db.permission.Resource.id).where(
                    db.permission.Resource.id.in_(change_resource_id_set),
                    ~db.permission.Resource.id.in_(
                        (
                            sqlalchemy.select(db.permission.Resource.id)
                            .join(db.permission.Rule)
                            .where(
                                db.permission.Resource.id.in_(change_resource_id_set),
                                db.permission.Rule.principal_id == principal_id,
                            )
                        )
                    ),
                )
            )
            # Insert any absent permission rows for the principal.
            insert_resource_id_set = {row for row, in result.all()}
            log.debug(f'insert_resource_id_set: {insert_resource_id_set}')
            if insert_resource_id_set:
                await self._session.execute(
                    sqlalchemy.insert(db.permission.Rule),
                    [
                        {
                            "resource_id": resource_id,
                            "principal_id": principal_id,
                            "permission": permission_level,
                        }
                        for resource_id in insert_resource_id_set
                    ],
                )
            # Update any existing permission rows for the principal.
            update_resource_id_set = change_resource_id_set - insert_resource_id_set
            log.debug(f'update_resource_id_set: {update_resource_id_set}')
            if update_resource_id_set:
                update_stmt = (
                    sqlalchemy.update(db.permission.Rule)
                    .where(
                        db.permission.Rule.resource_id.in_(update_resource_id_set),
                        db.permission.Rule.principal_id == principal_id,
                    )
                    .values(permission=permission_level)
                )
                await self._session.execute(update_stmt)

            # await self._session.flush()
            # await self._session.commit()
            # await self.commit()

    # async def set_permission_on_resource_list(
    #     self,
    #     token_profile_row,
    #     resource_list,
    #     principal_id,
    #     principal_type,
    #     permission_level,
    # ):
    #     """Update a permission level for a principal on a set of resources, designated by collection
    #      ID, and resource type.
    #
    #     :param token_profile_row: The profile of the user who is updating the permission. The user
    #     must have authenticated and must be holding a valid token for this profile.
    #     :param resource_list: [[parent_id, resource_type], ...]
    #     :param principal_id: The ID of the principal (profile or group) to grant the
    #     permission to.
    #     :param principal_type: The type of the principal (PROFILE or GROUP).
    #     :param permission_level: The permission level to grant (READ, WRITE, CHANGE).
    #     """
    #
    #     for parent_id, resource_type in resource_list:
    #         resource_row_query = (
    #             await self._session.query(db.permission.Resource)
    #             .filter(
    #                 db.permission.Resource.parent_id == parent_id,
    #                 db.permission.Resource.type == resource_type,
    #             )
    #             .all()
    #         )
    #         for resource_row in resource_row_query:
    #             await self._create_or_update_permission(
    #                 resource_row.id,
    #                 principal_id,
    #                 principal_type,
    #                 permission_level,
    #             )
    #
    #     await self.commit()

    async def _merge_profiles(self, token_profile_row, from_profile_row):
        """Merge from_profile into token_profile, then delete from_profile."""

        # Move all permissions granted to from_profile to the token_profile. Since corresponding
        # permissions may already exist for token_profile, we need to check if the permission
        # already exists and update it instead of creating a new one. We also need to keep only the
        # highest permission level.
        async for rule_row in await self._session.stream(
            (
                sqlalchemy.select(
                    db.permission.Rule,
                )
                .join(
                    db.permission.Resource,
                    db.permission.Resource.id == db.permission.Rule.resource_id,
                )
                .join(
                    db.permission.Principal,
                    db.permission.Principal.id == db.permission.Rule.principal_id,
                )
                .where(
                    db.permission.Principal.subject_id == from_profile_row.id,
                    db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
                )
            )
        ):
            await self._merge_profiles_set_permission(
                rule_row.resource, token_profile_row.principal, rule_row.permission
            )

        await self._delete_profile(from_profile_row)

    async def _delete_profile(self, profile_row):
        # Delete all rules for from_profile
        await self._session.execute(
            sqlalchemy.delete(db.permission.Rule).where(
                db.permission.Rule.principal_id == profile_row.principal.id
            )
        )
        # Delete all identities for from_profile
        await self._session.execute(
            sqlalchemy.delete(db.identity.Identity).where(
                db.identity.Identity.profile_id == profile_row.id
            )
        )
        # Delete all groups for from_profile
        await self._session.execute(
            sqlalchemy.delete(db.group.Group).where(db.group.Group.profile_id == profile_row.id)
        )
        # Delete all group memberships for from_profile
        await self._session.execute(
            sqlalchemy.delete(db.group.GroupMember).where(
                db.group.GroupMember.profile_id == profile_row.id
            )
        )
        # Delete the principal for from_profile
        await self._session.delete(profile_row.principal)
        # Delete the from_profile
        await self._session.delete(profile_row)

    async def _merge_profiles_set_permission(
        self,
        resource_row,
        principal_row,
        permission_level,
    ):
        """Ensure that principal_row has at least the given permission level on the resource.

        This is a no-op if the principal_row already has the given permission level or greater on
        the resource. This means that it is always a no-op if the permission level is 0 (NONE).

        If principal_row has no permission on the resource, a new rule is added with the given
        permission_level.
        """

        if permission_level == 0:
            return

        rule_row = await self._get_rule(resource_row, principal_row)

        if rule_row is None:
            rule_row = db.permission.Rule(
                resource=resource_row,
                principal=principal_row,
                permission=permission_level,
            )
            self._session.add(rule_row)
        else:
            rule_row.permission = max(rule_row.permission, permission_level)

    async def _create_or_update_permission(
        self,
        resource_row,
        principal_row,
        permission_level,
    ):
        """Create or update a permission for a principal on a resource.

        CHANGE permission on the resource must already have been validated before calling this
        method.

        This, and other methods of this class starting with underscore do not perform their own
        commit.
        """
        rule_row = await self._get_rule(resource_row, principal_row)

        if permission_level == 0:
            if rule_row is not None:
                await self._session.delete(rule_row)
        else:
            if rule_row is None:
                # principal_row = self.get_principal_by_subject(principal_row, principal_type)
                rule_row = db.permission.Rule(
                    resource=resource_row,
                    principal=principal_row,
                    permission=db.permission.PermissionLevel(permission_level),
                )
                self._session.add(rule_row)
            else:
                rule_row.permission = db.permission.PermissionLevel(permission_level)

    async def _get_rule(self, resource_row, principal_row):
        # The Rule table has a unique constraint on (resource_id, principal_id), so there will be 0
        # or 1 match to this query.
        result = await self._session.execute(
            (
                sqlalchemy.select(db.permission.Rule)
                .join(
                    db.permission.Principal,
                    db.permission.Principal.id == db.permission.Rule.principal_id,
                )
                .where(
                    db.permission.Rule.resource == resource_row,
                    db.permission.Principal == principal_row,
                )
            )
        )
        return result.scalars().first()

    async def get_resource_list(self, token_profile_row, search_str, resource_type):
        """Get a list of resources and permissions, with resource labels filtered on search_str.

        if search_str is False (None or ''), return all resources.

        - A resource contains zero to many permissions
        - A resource may have a parent resource, which is another resource
        - A permission contains one profile or one group
        """
        # SQLAlchemy automatically escapes parameters to prevent SQL injection attacks, but we still
        # need to escape the % and _ wildcards in the search string to preserve them as literals and
        # prevent unwanted wildcard matching.
        if search_str:
            search_str = re.sub(r'([%_])', r'\\\1', search_str)
        else:
            search_str = ''

        # Subquery to check if the token has CHANGE permission on the resource
        # token_has_change_permission_subquery = (
        #     sqlalchemy.select(db.permission.Resource.id)
        #     .join(db.permission.Rule)
        #     .join(
        #         db.permission.Principal,
        #         db.permission.Principal.id == db.permission.Rule.principal_id,
        #     )
        #     .where(
        #         db.permission.Principal.subject_id == token_profile_row.id,
        #         db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
        #         db.permission.Rule.permission == db.permission.PermissionLevel.CHANGE,
        #     )
        # )

        # Main query to fetch resources, rules and principals
        stmt = (
            sqlalchemy.select(
                db.permission.Resource,
                db.permission.Rule,
                db.permission.Principal,
                db.profile.Profile,
                db.group.Group,
            )
            .select_from(db.permission.Resource)
            # In SQLAlchemy, outerjoin() is a left join. Right join is not directly supported (have
            # to swap the order of the tables).
            .join(
                db.permission.Rule,
                db.permission.Rule.resource_id == db.permission.Resource.id,
            )
            .join(
                db.permission.Principal,
                db.permission.Principal.id == db.permission.Rule.principal_id,
            )
            .outerjoin(
                db.profile.Profile,
                sqlalchemy.and_(
                    db.profile.Profile.id == db.permission.Principal.subject_id,
                    db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
                ),
            )
            .outerjoin(
                db.group.Group,
                sqlalchemy.and_(
                    db.group.Group.id == db.permission.Principal.subject_id,
                    db.permission.Principal.subject_type == db.permission.SubjectType.GROUP,
                ),
            )
            # .where(
            #     db.permission.Resource.label.ilike(f'{search_str}%'),
            #     # db.permission.Resource.id.in_(token_has_change_permission_subquery),
            # )
        )

        # Filter by resource type if provided
        if resource_type is not None:
            stmt = stmt.where(db.permission.Resource.type == resource_type)

        # Add ordering to the query
        stmt = stmt.order_by(
            db.permission.Resource.type,
            db.permission.Resource.label,
            db.profile.Profile.common_name,
            db.profile.Profile.email,
        )

        result = await self._session.execute(stmt)
        return result.all()

    async def get_permission_generator(self, resource_ids):
        """Yield profiles and permissions for a list of resources."""
        for i in range(0, len(resource_ids), Config.DB_CHUNK_SIZE):
            resource_chunk_list = resource_ids[i : i + Config.DB_CHUNK_SIZE]

            stmt = (
                sqlalchemy.select(
                    db.permission.Resource,
                    db.permission.Rule,
                    db.permission.Principal,
                    db.profile.Profile,
                    db.group.Group,
                )
                .select_from(db.permission.Resource)
                .join(
                    db.permission.Rule,
                    db.permission.Rule.resource_id == db.permission.Resource.id,
                )
                .join(
                    db.permission.Principal,
                    db.permission.Principal.id == db.permission.Rule.principal_id,
                )
                .outerjoin(
                    db.profile.Profile,
                    sqlalchemy.and_(
                        db.profile.Profile.id == db.permission.Principal.subject_id,
                        db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
                    ),
                )
                .outerjoin(
                    db.group.Group,
                    sqlalchemy.and_(
                        db.group.Group.id == db.permission.Principal.subject_id,
                        db.permission.Principal.subject_type == db.permission.SubjectType.GROUP,
                    ),
                )
                .where(db.permission.Resource.id.in_(resource_chunk_list))
            )
            result = await self._session.stream(stmt)
            # async for row in result.scalars():
            async for row in result:
                yield row

    #
    # Principal
    #

    async def get_principal_id_query(self, token_profile_row):
        """Return a query that returns the principal IDs for all principals that the profile has
        access to.

        The returned list includes the principal IDs of:
            - The profile itself (the 'sub' field)
            - All groups in which this profile is a member (included in 'principals' field)
            - the Public Access profile  (included in 'principals' field)
            - the Authenticated Access profile  (included in 'principals' field)
        """
        return (
            sqlalchemy.select(db.permission.Principal.id)
            .outerjoin(
                db.profile.Profile,
                sqlalchemy.and_(
                    db.profile.Profile.id == db.permission.Principal.subject_id,
                    db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
                ),
            )
            .outerjoin(
                db.group.Group,
                sqlalchemy.and_(
                    db.group.Group.id == db.permission.Principal.subject_id,
                    db.permission.Principal.subject_type == db.permission.SubjectType.GROUP,
                ),
            )
            .outerjoin(
                db.group.GroupMember,
                sqlalchemy.and_(
                    db.group.GroupMember.group_id == db.group.Group.id,
                    db.group.GroupMember.profile_id == token_profile_row.id,
                ),
            )
            .where(
                sqlalchemy.or_(
                    # Principal ID of the Profile
                    sqlalchemy.and_(
                        db.permission.Principal.subject_id == token_profile_row.id,
                        db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
                    ),
                    # Public Access
                    sqlalchemy.and_(
                        db.permission.Principal.subject_id
                        == await util.profile_cache.get_public_access_profile_id(self),
                        db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
                    ),
                    # Authorized access
                    sqlalchemy.and_(
                        db.permission.Principal.subject_id
                        == await util.profile_cache.get_authenticated_access_profile_id(self),
                        db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
                    ),
                    # Groups in which the profile is a member
                    db.group.GroupMember.profile_id == token_profile_row.id,
                )
            )
        )

    async def get_equivalent_principal_edi_id_set(self, token_profile_row):
        """Get a set of EDI-IDs for all principals that the profile has access to.

        Note: This includes the EDI-ID for the profile itself, which should not be included in
        the 'principals' field of the JWT.
        """
        principal_ids = (
            (await self._session.execute(await self.get_principal_id_query(token_profile_row)))
            .scalars()
            .all()
        )

        stmt = (
            sqlalchemy.select(
                sqlalchemy.case(
                    (
                        db.permission.Principal.subject_type == db.permission.SubjectType.GROUP,
                        db.group.Group.edi_id,
                    ),
                    else_=db.profile.Profile.edi_id,
                )
            )
            .select_from(db.permission.Principal)
            .outerjoin(
                db.group.Group,
                sqlalchemy.and_(
                    db.group.Group.id == db.permission.Principal.subject_id,
                    db.permission.Principal.subject_type == db.permission.SubjectType.GROUP,
                ),
            )
            .outerjoin(
                db.profile.Profile,
                sqlalchemy.and_(
                    db.profile.Profile.id == db.permission.Principal.subject_id,
                    db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
                ),
            )
            .where(db.permission.Principal.id.in_(principal_ids))
        )

        return set((await self._session.execute(stmt)).scalars().all())

    async def _add_principal(self, subject_id, subject_type):
        """Insert a principal into the database.

        subject_id and subject_type are unique together.
        """
        new_principal_row = db.permission.Principal(
            subject_id=subject_id, subject_type=subject_type
        )
        self._session.add(new_principal_row)
        await self._session.flush()
        return new_principal_row

    async def get_principal(self, principal_id):
        """Get a principal by its ID."""
        result = await self._session.execute(
            sqlalchemy.select(db.permission.Principal).where(
                db.permission.Principal.id == principal_id
            )
        )
        return result.scalars().first()

    async def get_principal_by_subject(self, subject_id, subject_type):
        """Get a principal by its entity ID and type."""
        result = await self._session.execute(
            sqlalchemy.select(db.permission.Principal).where(
                db.permission.Principal.subject_id == subject_id,
                db.permission.Principal.subject_type == subject_type,
            )
        )
        return result.scalars().first()

    async def get_principal_by_profile(self, profile_row):
        """Get the principal for a profile."""
        result = await self._session.execute(
            sqlalchemy.select(db.permission.Principal).where(
                db.permission.Principal.subject_id == profile_row.id,
                db.permission.Principal.subject_type == db.permission.SubjectType.PROFILE,
            )
        )
        return result.scalars().first()

    #
    # Sync
    #

    async def sync_update(self, name):
        """Update or create a sync row with the given name."""
        result = await self._session.execute(
            sqlalchemy.select(db.sync.Sync).where(db.sync.Sync.name == name)
        )
        sync_row = result.scalars().first()
        if sync_row is None:
            sync_row = db.sync.Sync(name=name)
            self._session.add(sync_row)
        # No-op update to trigger onupdate
        sync_row.name = sync_row.name
        await self.commit()

    async def get_sync_ts(self):
        """Get the latest timestamp."""
        result = await self._session.execute(
            sqlalchemy.select(sqlalchemy.func.max(db.sync.Sync.updated))
        )
        return result.scalar()

    #
    # Util
    #

    async def rollback(self):
        """Roll back the current transaction."""
        return await self._session.rollback()

    async def commit(self):
        """Commit the current transaction."""
        log.debug('# COMMIT #')
        # return await self._session.commit()
