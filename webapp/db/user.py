import datetime
import uuid

import daiquiri
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.orm
import sqlalchemy.pool

import db.base
import db.group
import db.identity
import db.permission
import db.profile
import db.sync
import util.avatar
from config import Config

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class UserDb:
    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session

    #
    # Profile and Identity
    #

    def create_or_update_profile_and_identity(
        self,
        full_name: str,
        idp_name: str,
        idp_uid: str,
        email: str | None,
        has_avatar: bool,
    ) -> db.identity.Identity:
        """Create or update a profile and identity.

        See the table definitions for Profile and Identity for more information on the
        fields.
        """
        identity_row = self.get_identity(idp_name=idp_name, idp_uid=idp_uid)
        # Split a full name in to given name and family name. If full_name is a single
        # word, family_name will be None. If full_name is multiple words, the first word
        # will be given_name and the remaining words will be family_name.
        given_name, family_name = full_name.split(' ', 1) if ' ' in full_name else (full_name, None)
        if identity_row is None:
            profile_row = self.create_profile(
                pasta_id=self.get_new_pasta_id(),
                given_name=given_name,
                family_name=family_name,
                email=email,
                has_avatar=has_avatar,
            )
            identity_row = self.create_identity(
                profile=profile_row,
                idp_name=idp_name,
                idp_uid=idp_uid,
                email=email,
                has_avatar=has_avatar,
            )
            # Set the avatar for the profile to the avatar for the identity
            if has_avatar:
                avatar_img = util.avatar.get_avatar_path(idp_name, idp_uid).read_bytes()
                util.avatar.save_avatar(avatar_img, 'profile', profile_row.pasta_id)
        else:
            # We do not update the profile if it exists, since the profile belongs to
            # the user, and they may update their profile with their own information.
            self.update_identity(identity_row, idp_name, idp_uid, email, has_avatar)

        return identity_row

    #
    # Profile
    #

    def create_profile(
        self,
        pasta_id: str,
        given_name: str = None,
        family_name: str = None,
        email: str = None,
        has_avatar: bool = False,
    ):
        new_profile_row = db.profile.Profile(
            pasta_id=pasta_id,
            given_name=given_name,
            family_name=family_name,
            email=email,
            has_avatar=has_avatar,
        )
        self.session.add(new_profile_row)
        self.session.commit()
        self.sync_update('profile')
        return new_profile_row

    def get_public_profile(self):
        """Get the profile for the public user."""
        return (
            self.session.query(db.profile.Profile)
            .filter(db.profile.Profile.pasta_id == Config.PUBLIC_PASTA_ID)
            .first()
        )

    def create_public_profile(self):
        try:
            self.create_profile(
                pasta_id=Config.PUBLIC_PASTA_ID,
                given_name=Config.PUBLIC_NAME,
                has_avatar=True,
            )
        except sqlalchemy.exc.IntegrityError:
            self.session.rollback()
        else:
            util.avatar.init_public_avatar()

    def get_profile(self, pasta_id):
        return (
            self.session.query(db.profile.Profile)
            .filter(db.profile.Profile.pasta_id == pasta_id)
            .first()
        )

    def get_profiles_by_ids(self, profile_id_list):
        """Get a list of profiles by their IDs.
        The list is returned in the order of the IDs in the input list.
        """
        profile_query = (
            self.session.query(db.profile.Profile)
            .filter(db.profile.Profile.id.in_(profile_id_list))
            .all()
        )
        profile_dict = {p.id: p for p in profile_query}
        return [
            profile_dict[profile_id] for profile_id in profile_id_list if profile_id in profile_dict
        ]

    def update_profile(self, token_profile_row, **kwargs):
        for key, value in kwargs.items():
            setattr(token_profile_row, key, value)
        self.session.commit()
        self.sync_update('profile')

    def delete_profile(self, token_profile_row):
        self.session.delete(token_profile_row)
        self.session.commit()
        self.sync_update('profile')

    def set_privacy_policy_accepted(self, token_profile_row):
        token_profile_row.privacy_policy_accepted = True
        token_profile_row.privacy_policy_accepted_date = datetime.datetime.now()
        self.session.commit()

    #
    # Identity
    #

    def create_identity(
        self,
        profile,
        idp_name: str,
        idp_uid: str,
        email: str,
        has_avatar: bool,
    ):
        """Create a new identity for a given profile."""
        new_identity = db.identity.Identity(
            profile=profile,
            idp_name=idp_name,
            idp_uid=idp_uid,
            email=email,
            has_avatar=has_avatar,
        )
        self.session.add(new_identity)
        self.session.commit()
        self.sync_update('identity')
        return new_identity

    def update_identity(self, identity_row, idp_name, idp_uid, email, has_avatar):
        assert identity_row.profile is not None
        assert identity_row.idp_name == idp_name
        assert identity_row.idp_uid == idp_uid
        # We always update the email address in the identity row, but only update the profile if the
        # profile is new. So if the user has changed their email address with the IdP, the new email
        # address will be stored in the identity row, but the profile will retain the original email
        # address.
        identity_row.email = email
        # Normally, has_avatar will be True from the first time the user logs in with the identity.
        # More rarely, it will go from False to True, if a user did not initially have an avatar at
        # the IdP, but then creates one. More rarely still (if at all possible), this may go from
        # True to False, if the user removes their avatar at the IdP. In this latter case, the
        # avatar image in the filesystem will be orphaned here.
        identity_row.has_avatar = has_avatar
        self.session.commit()
        self.sync_update('identity')

    def get_identity(self, idp_name: str, idp_uid: str):
        return (
            self.session.query(db.identity.Identity)
            .filter(
                db.identity.Identity.idp_name == idp_name,
                db.identity.Identity.idp_uid == idp_uid,
            )
            .first()
        )

    def get_identity_by_id(self, identity_id):
        return (
            self.session.query(db.identity.Identity)
            .filter(db.identity.Identity.id == identity_id)
            .first()
        )

    def delete_identity(self, profile_row, idp_name: str, idp_uid: str):
        """Delete an identity."""
        identity_row = self.get_identity(idp_name, idp_uid)
        if identity_row not in profile_row.identities:
            raise ValueError(f'Identity {idp_name} {idp_uid} does not belong to profile')
        self.session.delete(identity_row)
        self.session.commit()
        self.sync_update('identity')

    @staticmethod
    def get_new_pasta_id():
        return f'PASTA-{uuid.uuid4().hex}'

    def get_all_profiles(self):
        return (
            self.session.query(db.profile.Profile)
            .order_by(sqlalchemy.asc(db.profile.Profile.id))
            .all()
        )

    def get_all_profiles_generator(self):
        """Get a generator of all profiles, sorted by name, email, with id as tiebreaker."""
        for profile_row in self.session.query(db.profile.Profile).order_by(
            db.profile.Profile.given_name,
            db.profile.Profile.family_name,
            db.profile.Profile.email,
            db.profile.Profile.id,
        ):
            yield profile_row

    #
    # Group
    #

    def create_group(self, profile_row, name, description):
        new_group = db.group.Group(
            pasta_id=UserDb.get_new_pasta_id(),
            profile=profile_row,
            name=name,
            description=description or None,
        )
        self.session.add(new_group)
        self.session.commit()
        self.sync_update('group')
        return new_group

    def get_group(self, profile_row, group_id):
        """Get a group by its ID.
        Raises an exception if the group is not owned by the profile.
        """
        group_row = (
            self.session.query(db.group.Group)
            .filter(
                db.group.Group.id == group_id,
                db.group.Group.profile_id == profile_row.id,
            )
            .first()
        )
        if group_row is None:
            raise ValueError(f'Group {group_id} not found')
        return group_row

    def update_group(self, profile_row, group_id, name, description):
        """Update a group by its ID.
        Raises ValueError if the group is not owned by the profile.
        """
        group_row = self.get_group(profile_row, group_id)
        group_row.name = name
        group_row.description = description or None
        self.session.commit()
        self.sync_update('group')

    def delete_group(self, profile_row, group_id):
        """Delete a group by its ID.
        Raises ValueError if the group is not owned by the profile.
        """
        group_row = self.get_group(profile_row, group_id)
        # Delete group members
        self.session.query(db.group.GroupMember).filter(
            db.group.GroupMember.group_id == group_row.id
        ).delete()
        self.session.delete(group_row)
        self.session.commit()
        self.sync_update('group')

    def add_group_member(self, profile_row, group_id, member_profile_id):
        """Add a member to a group.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the profile
        group_row = self.get_group(profile_row, group_id)
        new_member = db.group.GroupMember(
            group=group_row,
            profile_id=member_profile_id,
        )
        self.session.add(new_member)
        group_row.updated = datetime.datetime.now()
        self.session.commit()
        self.sync_update('group_member')

    def delete_group_member(self, profile_row, group_id, member_profile_id):
        """Delete a member from a group.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the profile
        group_row = self.get_group(profile_row, group_id)
        member_row = (
            self.session.query(db.group.GroupMember)
            .filter(
                db.group.GroupMember.group_id == group_row.id,
                db.group.GroupMember.profile_id == member_profile_id,
            )
            .first()
        )
        if member_row is None:
            raise ValueError(f'Member {member_profile_id} not found in group {group_id}')
        self.session.delete(member_row)
        group_row.updated = datetime.datetime.now()
        self.session.commit()
        self.sync_update('group_member')

    def get_group_member_list(self, profile_row, group_id):
        """Get the members of a group.
        Raises ValueError if the group is not owned by the profile.
        """
        group_row = self.get_group(profile_row, group_id)
        query = self.session.query(db.group.GroupMember)
        return query.filter(db.group.GroupMember.group == group_row).all()

    def get_group_membership_list(self, profile_row):
        """Get the groups that this profile is a member of."""
        return (
            self.session.query(db.group.Group)
            .join(db.group.GroupMember)
            .filter(db.group.GroupMember.profile == profile_row)
            .all()
        )

    def get_group_membership_pasta_id_set(self, profile_row):
        return {group.pasta_id for group in self.get_group_membership_list(profile_row)}

    def leave_group_membership(self, profile_row, group_id):
        """Leave a group.
        Raises ValueError if the member who is leaving does match the profile.

        Note: While this method ultimately performs the same action as delete_group_member,
        it performs different checks.
        """
        member_row = (
            self.session.query(db.group.GroupMember)
            .filter(
                db.group.GroupMember.group_id == group_id,
                db.group.GroupMember.profile_id == profile_row.id,
            )
            .first()
        )
        if member_row is None:
            raise ValueError(f'Member {profile_row.id} not found in group {group_id}')
        member_row.group.updated = datetime.datetime.now()
        self.session.delete(member_row)
        self.session.commit()
        self.sync_update('group_member')

    def get_all_groups_generator(self):
        for group_row in (
            self.session.query(db.group.Group)
            .options(sqlalchemy.orm.joinedload(db.group.Group.profile))
            .order_by(
                db.group.Group.name,
                db.group.Group.description,
                sqlalchemy.asc(db.group.Group.created),
                db.group.Group.id,
            )
        ):
            yield group_row

    #
    # Permission
    #

    async def get_resource_list_by_collection_and_type_query(
        self,
        collection_id,
        resource_type,
    ):
        """Get a list of resources by collection ID and resource type."""
        return self.session.query(db.permission.Resource).filter(
            db.permission.Resource.collection_id == collection_id,
            db.permission.Resource.type == resource_type,
        )

    async def set_permission_by_resource_list(
        self,
        token_profile_row,
        resource_ids,
        principal_id,
        principal_type,
        permission_level,
    ):
        """Securely set the permission level for a principal on a set of resources designated by
         resource IDs.

        Postconditions:
            - permission_level == 0: No permission rows will exist for the principal on the
            resources in resource_list.
            - permission_level > 0: A permission row for each resource in resource_list, with the
            given principal and permission_level will exist.

        If the token_profile_row does not have OWN permission for a resource, the resource will
        be silently ignored and any existing permission rows for that resource will not be changed.
        This is to prevent a user from granting themselves permissions they do not have.

        If a resource does not exist, it will be silently ignored.

        :param token_profile_row: The profile of the user who is updating the permission. The user
        must have authenticated and must be holding a valid token for this profile.
        :param resource_ids: A sequence of resource IDs to grant the permission on.
        :param principal_id: The ID of the principal (profile or group) to grant the permission to.
        :param principal_type: The type of the principal (PROFILE or GROUP).
        :param permission_level: The permission level to grant (READ, WRITE, OWN).
        """
        # Databases have a limit to the number of parameters they can accept in a single query, so
        # we chunk the list of resource IDs, which then also limits the number of rows we attempt to
        # create or update in a single bulk query.
        for i in range(0, len(resource_ids), Config.DB_CHUNK_SIZE):
            resource_chunk_list = resource_ids[i : i + Config.DB_CHUNK_SIZE]
            # Filter the resource_chunk_list to only include resources for which the
            # token_profile_row has OWN permission (which also filters out any non-existing
            # resource IDs).
            secure_resource_id_set = set(
                self.session.query(
                    db.permission.Resource.id,
                )
                .join(
                    db.permission.Permission,
                    db.permission.Permission.resource_id == db.permission.Resource.id,
                )
                .filter(
                    db.permission.Resource.id.in_(resource_chunk_list),
                    db.permission.Permission.principal_id == token_profile_row.id,
                    db.permission.Permission.principal_type == db.permission.PrincipalType.PROFILE,
                    db.permission.Permission.level >= db.permission.PermissionLevel.OWN,
                )
                .all()
            )
            if permission_level == 0:
                self.session.query(db.permission.Permission).filter(
                    db.permission.Permission.resource_id.in_(secure_resource_id_set),
                    db.permission.Permission.principal_id == principal_id,
                    db.permission.Permission.principal_type == principal_type,
                ).delete()
            else:
                # Create a resource_id_list that only includes the resource IDs for which there
                # are no existing permission rows for the principal.
                insert_resource_id_set = set(
                    self.session.query(
                        db.permission.Permission.resource_id,
                    )
                    .outerjoin(
                        db.permission.Permission,
                        db.permission.Permission.resource_id == db.permission.Resource.id,
                    )
                    .filter(
                        ~(
                            db.permission.Permission.resource_id.in_(secure_resource_id_set),
                            db.permission.Permission.principal_id == principal_id,
                            db.permission.Permission.principal_type == principal_type,
                        )
                    )
                    .all()
                )
                # Insert any 'missing' permission rows for the principal.
                log.debug(f'insert_resource_id_set: {sorted(insert_resource_id_set)}')
                self.session.bulk_insert_mappings(
                    db.permission.Permission,
                    [
                        {
                            'resource_id': resource_id,
                            'principal_id': principal_id,
                            'principal_type': principal_type,
                            'level': permission_level,
                        }
                        for resource_id, in insert_resource_id_set
                    ],
                )
                # Update any existing permission rows for the principal.
                update_resource_id_set = secure_resource_id_set - insert_resource_id_set
                log.debug(f'update_resource_id_set: {sorted(update_resource_id_set)}')
                (
                    self.session.query(
                        db.permission.Permission,
                    )
                    .filter(
                        db.permission.Permission.resource_id.in_(update_resource_id_set),
                        db.permission.Permission.principal_id == principal_id,
                        db.permission.Permission.principal_type == principal_type,
                    )
                    .update(
                        {
                            db.permission.Permission.level: permission_level,
                        },
                        synchronize_session=False,
                    )
                )

            self.session.commit()
            self.sync_update('permission')

    async def set_permission_on_resource_list(
        self,
        token_profile_row,
        resource_list,
        principal_id,
        principal_type,
        permission_level,
    ):
        """Update a permission level for a principal on a set of resources, designated by collection
         ID, and resource type.

        :param token_profile_row: The profile of the user who is updating the permission. The user
        must have authenticated and must be holding a valid token for this profile.
        :param resource_list: [[collection_id, resource_type], ...]
        :param principal_id: The ID of the principal (profile or group) to grant the
        permission to.
        :param principal_type: The type of the principal (PROFILE or GROUP).
        :param permission_level: The permission level to grant (READ, WRITE, OWN).
        """
        for collection_id, resource_type in resource_list:
            resource_row_query = (
                self.session.query(db.permission.Resource)
                .filter(
                    db.permission.Resource.collection_id == collection_id,
                    db.permission.Resource.type == resource_type,
                )
                .all()
            )
            for resource_row in resource_row_query:
                self._create_or_update_permission(
                    resource_row.id,
                    principal_id,
                    principal_type,
                    permission_level,
                )

        self.session.commit()
        self.sync_update('permission')

    def _create_or_update_permission(
        self,
        resource_row,
        principal_id,
        principal_type,
        permission_level,
    ):
        principal_enum = db.permission.PrincipalType[principal_type.upper()]
        permission_row = self._get_permission(resource_row, principal_id, principal_enum)

        if permission_level == 0:
            if permission_row is not None:
                self.session.delete(permission_row)
        else:
            if permission_row is None:
                permission_row = db.permission.Permission(
                    resource=resource_row,
                    principal_id=principal_id,
                    principal_type=principal_enum,
                    level=db.permission.PermissionLevel(permission_level),
                )
                self.session.add(permission_row)
            else:
                permission_row.level = db.permission.PermissionLevel(permission_level)

    def _get_permission(self, resource_id, principal_id, principal_enum):
        # The Permission table has a unique constraint on (resource_id, principal_id, principal_type),
        # so there will be 0 or 1 match to this query.
        return (
            self.session.query(db.permission.Permission).filter(
                db.permission.Permission.resource_id == resource_id,
                db.permission.Permission.principal_id == principal_id,
                db.permission.Permission.principal_type == principal_enum,
            )
        ).first()

    #
    # Collection
    #

    async def get_resource_list(self, token_profile_row, search_str):
        """Get a list of resources, with collection and permissions, with collection labels matching
         search_str.

        if search_str is False (None or ''), return all resources.

        - A collection contains zero to many resources
        - A resource contains zero to many permissions
        - A permission contains one profile, or one group
        """
        # SQLAlchemy automatically escapes parameters to prevent SQL injection attacks, but we still
        # need to escape the % and _ wildcards in the search string to preserve them as literals and
        # prevent unwanted wildcard matching.
        search_str = (
            search_str.replace("%", "\\%").replace("_", "\\_")
            # TODO: Check if required
            # .replace("\\", "\\\\")
            # .replace("'", "''")
        )

        return (
            self.session.query(
                db.permission.Collection,
                db.permission.Resource,
                db.permission.Permission,
                db.profile.Profile,
                db.group.Group,
            )
            .select_from(db.permission.Collection)
            # In SQLAlchemy, outerjoin() is a left join. Right join is not directly
            # supported (have to swap the order of the tables).
            .outerjoin(
                db.permission.Resource,
                db.permission.Collection.id == db.permission.Resource.collection_id,
            )
            .outerjoin(
                db.permission.Permission,
                db.permission.Resource.id == db.permission.Permission.resource_id,
            )
            .outerjoin(
                db.profile.Profile,
                sqlalchemy.and_(
                    db.permission.Permission.principal_id == db.profile.Profile.id,
                    db.permission.Permission.principal_type == db.permission.PrincipalType.PROFILE,
                ),
            )
            .outerjoin(
                db.group.Group,
                sqlalchemy.and_(
                    db.permission.Permission.principal_id == db.group.Group.id,
                    db.permission.Permission.principal_type == db.permission.PrincipalType.GROUP,
                ),
            )
            .filter(db.permission.Collection.label.ilike(f'{search_str}%'))
            .order_by(
                db.permission.Collection.label,
                db.permission.Collection.type,
                db.permission.Collection.created_date,
                db.permission.Resource.type,
                db.permission.Resource.label,
                db.profile.Profile.given_name,
                db.profile.Profile.family_name,
            )
        )

    def get_permission_generator(self, resource_ids):
        """Yield profiles and permissions for a list of resources.
        """
        for i in range(0, len(resource_ids), Config.DB_CHUNK_SIZE):
            resource_chunk_list = resource_ids[i : i + Config.DB_CHUNK_SIZE]

            query = (
                self.session.query(
                    db.permission.Collection,
                    db.permission.Resource,
                    db.permission.Permission,
                    db.profile.Profile,
                    db.group.Group,
                )
                .join(
                    db.permission.Resource,
                    db.permission.Collection.id == db.permission.Resource.collection_id,
                )
                .join(
                    db.permission.Permission,
                    db.permission.Resource.id == db.permission.Permission.resource_id,
                )
                .outerjoin(
                    db.profile.Profile,
                    sqlalchemy.and_(
                        db.permission.Permission.principal_id == db.profile.Profile.id,
                        db.permission.Permission.principal_type == db.permission.PrincipalType.PROFILE,
                    ),
                )
                .outerjoin(
                    db.group.Group,
                    sqlalchemy.and_(
                        db.permission.Permission.principal_id == db.group.Group.id,
                        db.permission.Permission.principal_type == db.permission.PrincipalType.GROUP,
                    ),
                )
                .filter(
                    db.permission.Resource.id.in_(resource_chunk_list)
                )
            )

            for row in query.yield_per(Config.DB_YIELD_ROWS):
                yield row

    #
    # Sync
    #

    def sync_update(self, name):
        """Update the timestamp on name"""
        sync_row = self.session.query(db.sync.Sync).filter_by(name=name).first()
        if sync_row is None:
            sync_row = db.sync.Sync(name=name)
            self.session.add(sync_row)
        # No-op update to trigger onupdate
        sync_row.name = sync_row.name
        self.session.commit()

    def get_sync_ts(self):
        """Get the latest timestamp"""
        return self.session.query(sqlalchemy.func.max(db.sync.Sync.updated)).scalar()
