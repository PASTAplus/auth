import datetime
import uuid

import daiquiri
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.orm
import sqlalchemy.pool

import db.base
import db.group
import db.identity
import db.permission
import db.profile
import db.sync
import util.avatar

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker
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
        given_name, family_name = (
            full_name.split(' ', 1) if ' ' in full_name else (full_name, None)
        )
        if identity_row is None:
            profile_row = self.create_profile(
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
        given_name: str = None,
        family_name: str = None,
        email: str = None,
        has_avatar: bool = False,
    ):
        new_profile = db.profile.Profile(
            pasta_id=UserDb.get_new_pasta_id(),
            given_name=given_name,
            family_name=family_name,
            email=email,
            has_avatar=has_avatar,
        )
        self.session.add(new_profile)
        self.session.commit()
        self.sync_update('profile')
        return new_profile

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
            profile_dict[profile_id]
            for profile_id in profile_id_list
            if profile_id in profile_dict
        ]

    def has_profile(self, pasta_id):
        return self.get_profile(pasta_id) is not None

    def update_profile(self, pasta_id, **kwargs):
        profile_row = self.get_profile(pasta_id)
        for key, value in kwargs.items():
            setattr(profile_row, key, value)
        self.session.commit()
        self.sync_update('profile')

    def delete_profile(self, pasta_id):
        profile_row = self.get_profile(pasta_id)
        self.session.delete(profile_row)
        self.session.commit()
        self.sync_update('profile')

    def set_privacy_policy_accepted(self, pasta_id):
        log.debug('Setting privacy policy accepted')
        profile_row = self.get_profile(pasta_id)
        profile_row.privacy_policy_accepted = True
        profile_row.privacy_policy_accepted_date = datetime.datetime.now()
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
            raise ValueError(
                f'Identity {idp_name} {idp_uid} does not belong to profile'
            )
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
            raise ValueError(
                f'Member {member_profile_id} not found in group {group_id}'
            )
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

    #
    # Permission
    #

    # def get_permission_list(self, resource_row):
    #     return (
    #         self.session.query(db.permission.Permission)
    #         .join(
    #             db.profile.Profile,
    #             db.permission.Permission.grantee_id == db.profile.Profile.id,
    #         )
    #         .filter(db.permission.Permission.resource == resource_row)
    #         # order_by can only accept column names, not dynamic properties like full_name.
    #         .order_by(
    #             db.profile.Profile.given_name,
    #             db.profile.Profile.family_name,
    #             db.profile.Profile.id,
    #         )
    #         .all()
    #     )

    # def get_resource(self, resource_id):
    #     return (
    #         self.session.query(db.permission.Resource)
    #         .filter(db.permission.Resource.id == resource_id)
    #         .first()
    #     )

    # def get_permission(self, permission_id):
    #     return (
    #         self.session.query(db.permission.Permission)
    #         .filter(db.permission.Permission.id == permission_id)
    #         .first()
    #     )

    # def create_permission(self, resource_id, profile_id):
    #     """Create a new READ permission"""
    #     new_permission = db.permission.Permission(
    #         resource_id=resource_id,
    #         profile_id=profile_id,
    #         level=1,
    #     )
    #     self.session.add(new_permission)
    #     self.session.commit()
    #     self.sync_update('permission')
    #     return new_permission

    ###########

    # def update_permission(
    #     self, profile_row, resource_list, profile_id, permission_level
    # ):
    #     """Update a permission level for a profile.
    #
    #     There are 2 profiles:
    #     - The profile of the user who is updating the permission (profile_row).
    #     - The profile of the user who is granted the permission.
    #
    #     resource_list contains a list of lists of [collection_id, resource_type].
    #     """
    #     # return
    #
    #     collection_id_list = {r[0] for r in resource_list}
    #
    #     query = (
    #         self.session.query(
    #             db.permission.Collection,
    #             db.permission.Resource,
    #             db.permission.Permission,
    #             db.profile.Profile,
    #         )
    #         .outerjoin(
    #             db.permission.Resource,
    #             db.permission.Collection.id == db.permission.Resource.collection_id,
    #         )
    #         .outerjoin(
    #             db.permission.Permission,
    #             db.permission.Resource.id == db.permission.Permission.resource_id,
    #         )
    #         .outerjoin(
    #             db.profile.Profile,
    #             db.permission.Permission.profile_id == db.profile.Profile.id,
    #         )
    #         .filter(db.permission.Collection.id.in_(collection_id_list))
    #         .order_by(
    #             db.permission.Collection.label,
    #             db.permission.Collection.type,
    #             db.permission.Collection.created_date,
    #             db.permission.Resource.type,
    #             db.permission.Resource.label,
    #             db.profile.Profile.given_name,
    #             db.profile.Profile.family_name,
    #         )
    #         .all()
    #     )
    #
    #     pprint.pp(query, width=1)
    #
    #     # Iterate over all the resources in all the collections.
    #     # If a permission row exists for the profile:
    #     #   If the new permission is 0, delete the permission_row, else update it.
    #     # If a permission row does NOT exist for the profile:
    #     #   Create a new permission row.
    #     for collection_row, resource_row, permission_row, profile_row in query:
    #         # TODO: Use set
    #         if [collection_row.id, resource_row.type] not in resource_list:
    #             continue
    #
    #         # if permission_level == 0:
    #         #     self.delete_permission(permission_row)
    #         #     continue
    #         #
    #         # if not permission_row:
    #         #     continue
    #
    #         permission_row.permission_level = permission_level
    #
    #         self.session.commit()
    #
    #         # for collection_id, resource_type in resource_list:
    #         #     if resource_row.type != resource_type:
    #         #         continue
    #         #
    #         #
    #         #     # if collection_row.id != collection_id:
    #         #     #     continue
    #         #
    #         #     # permission_row = self.get_permission_by_profile(resource_id, profile_id)
    #         #
    #         #     if permission_level == 0:
    #         #         return self.delete_permission(permission_row)
    #         #
    #         #     if not permission_row:
    #         #         permission_row = self.create_permission(resource_row.id, profile_id)
    #         #
    #         #     # if permission_row.profile != profile_row:
    #         #     #     raise ValueError('Permission does not belong to profile')
    #
    #     self.session.commit()
    #     self.sync_update('permission')

    async def update_permission(
        self, token_profile_row, resource_list, profile_id, permission_level
    ):
        """Update a permission level for a profile.

        :param token_profile_row: The profile of the user who is updating the
        permission. The user must have authenticated and must have a valid token for
        this profile.

        :param resource_list: A list of lists of [collection_id, resource_type].
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
                self._set_permission(
                    token_profile_row, resource_row.id, profile_id, permission_level
                )

        self.session.commit()

        # agg_perm_list = await self.get_aggregate_profile_permission_list(resource_list)
        #
        # for collection_id, resource_type in resource_list:
        #     resource_row_query = (
        #         self.session.query(db.permission.Resource)
        #         .filter(
        #             db.permission.Resource.collection_id == collection_id,
        #             db.permission.Resource.type == resource_type,
        #         )
        #         .all()
        #     )
        #     for resource_row in resource_row_query:
        #         for aggy in agg_perm_list:
        #             self._set_permission(
        #                 token_profile_row, resource_row.id, aggy['profile_id'], aggy['permission_level']
        #             )

        self.session.commit()
        self.sync_update('permission')

    def _set_permission(
        self, token_profile_row, resource_id, profile_id, permission_level
    ):
        # TODO: Check that token_profile_row has CHANGE permission for resource_id.
        permission_row = self._get_permission(resource_id, profile_id)

        if permission_level == 0:
            if permission_row is not None:
                self.session.delete(permission_row)
        else:
            if permission_row is None:
                permission_row = db.permission.Permission(
                    resource_id=resource_id,
                    grantee_id=profile_id,
                    grantee_type=db.permission.GranteeType.PROFILE,
                    level=db.permission.PermissionLevel(permission_level),
                )
                self.session.add(permission_row)
            else:
                permission_row.level = db.permission.PermissionLevel(permission_level)

    def _get_permission(self, resource_id, profile_id):
        # The Permission table has a unique constraint on (resource_id, profile_id).
        return (
            self.session.query(db.permission.Permission).filter(
                db.permission.Permission.resource_id == resource_id,
                db.permission.Permission.grantee_id == profile_id,
            )
        ).first()

    #
    # Collection
    #

    async def get_aggregate_collection_dict(self, profile_row, search_str):
        """Get a list of collections with nested resources and permissions. The
         permissions are aggregated by profile, and only the highest permission level
         is returned for each profile and resource type.

        In the DB:

        - A collection contains zero to many resources
        - A resource contains zero to many permissions
        - A permission contains one profile, or one group, or one public permission

        We return:

        - A dict of collections
        - Each collection contains a dict of resource types
        - Each resource type contains a dict of resources
        - Each resource contains a dict of profiles
        - Each profile contains the max permission level found for that profile in the
          resource type
        """
        # SQLAlchemy automatically escapes parameters to prevent SQL injection attacks,
        # but we still need to escape the % and _ wildcards in the search string to
        # preserve them as literals and prevent unwanted wildcard matching.
        search_str = (
            search_str.replace("%", "\\%").replace("_", "\\_")
            # TODO: Check if required
            # .replace("\\", "\\\\")
            # .replace("'", "''")
        )

        # We issue a simple join query, then we iterate over the results and build a
        # nested dictionary that removes the redundant information in the join result.
        # We could issue a more complex query that pushes the aggregation to the DB, but
        # this is much simpler, at the cost of some redundant information going over the
        # network.

        query = (
            # We assign labels as SQLAlchemy gets confused by multiple columns with the
            # same name (which we get after join for the id, label and type fields). We
            # could assign only the columns that are ambiguous, but we assign all for
            # consistency.
            self.session.query(
                db.permission.Collection,
                db.permission.Resource,
                db.permission.Permission,
                db.profile.Profile,
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
                    db.permission.Permission.grantee_id == db.profile.Profile.id,
                    db.permission.Permission.grantee_type
                    == db.permission.GranteeType.PROFILE,
                ),
            )
            .outerjoin(
                db.group.Group,
                sqlalchemy.and_(
                    db.permission.Permission.grantee_id == db.group.Group.id,
                    db.permission.Permission.grantee_type
                    == db.permission.GranteeType.GROUP,
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
            .all()
        )

        # log.debug(query)

        # Dicts preserve insertion order, so the dict structure will mirror the order in
        # the order_by clause. The order will also carry over to the JSON output.

        collection_dict = {}

        for (
            collection,
            resource,
            permission,
            profile,
        ) in query:
            resource_dict = collection_dict.setdefault(
                collection.id,
                {
                    'collection_label': collection.label,
                    'collection_type': collection.type,
                    'resource_dict': {},
                },
            )['resource_dict']

            # if resource.type is None:
            if resource is None:
                continue

            permission_dict = resource_dict.setdefault(
                resource.type,
                {
                    'resource_id_dict': {},
                    'profile_dict': {},
                },
            )

            permission_dict['resource_id_dict'][resource.id] = resource.label

            if permission is None:
                continue

            profile_dict = permission_dict['profile_dict']

            profile_dict.setdefault(
                profile.id,
                {
                    'pasta_id': profile.pasta_id,
                    'full_name': profile.full_name,
                    'permission_level': permission.level.value,
                },
            )

            profile_dict[profile.id]['permission_level'] = max(
                profile_dict[profile.id]['permission_level'], permission.level.value
            )

        # Iterate over profile_dict and convert them to lists sorted by full_name.
        for collection_id, collection in collection_dict.items():
            for resource_type, resource in collection['resource_dict'].items():
                profile_list = list(resource['profile_dict'].values())
                profile_list.sort(key=lambda p: p['full_name'])
                resource['profile_list'] = profile_list
                del resource['profile_dict']

        return collection_dict

    async def get_aggregate_profile_permission_list(self, resource_list):
        """Get a list of aggregated maximum profiles and permissions for a list of
        resources.

        :param resource_list: [[collection_id, resource_type], ...]
        """
        collection_id_list = {r[0] for r in resource_list}

        query = (
            self.session.query(
                db.permission.Collection,
                db.permission.Resource,
                db.permission.Permission,
                db.profile.Profile,
            )
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
                    db.permission.Permission.grantee_id == db.profile.Profile.id,
                    db.permission.Permission.grantee_type
                    == db.permission.GranteeType.PROFILE,
                ),
            )
            .outerjoin(
                db.group.Group,
                sqlalchemy.and_(
                    db.permission.Permission.grantee_id == db.group.Group.id,
                    db.permission.Permission.grantee_type
                    == db.permission.GranteeType.GROUP,
                ),
            )
            .filter(db.permission.Collection.id.in_(collection_id_list))
            .all()
        )

        profile_dict = {}

        for (collection_row, resource_row, permission_row, profile_row) in query:
            if [collection_row.id, resource_row.type] not in resource_list:
                continue

            if permission_row is None:
                continue

            if profile_row is None:
                continue

            profile_dict.setdefault(
                profile_row.id,
                {
                    'permission_id': permission_row.id,
                    'profile_id': profile_row.id,
                    'pasta_id': profile_row.pasta_id,
                    'full_name': profile_row.full_name,
                    'email': profile_row.email,
                    'avatar_url': profile_row.avatar_url,
                    'permission_level': permission_row.level.value,
                },
            )

            profile_dict[profile_row.id]['permission_level'] = max(
                profile_dict[profile_row.id]['permission_level'],
                permission_row.level.value,
            )

        return sorted(profile_dict.values(), key=lambda p: p['full_name'])
