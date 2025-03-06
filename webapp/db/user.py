import datetime
import uuid

import daiquiri
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.orm
import sqlalchemy.pool
import sqlalchemy.exc

import db.base
import db.group
import db.identity
import db.permission
import db.profile
import db.sync
import util.avatar
from config import Config

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
    # Permission
    #

    async def update_permission(
        self,
        token_profile_row,
        resource_list,
        principal_id,
        principal_type,
        permission_level,
    ):
        """Update a permission level for a principal.

        :param token_profile_row: The profile of the user who is updating the
        permission. The user must have authenticated and must have a valid token for
        this profile.

        :param resource_list: [[collection_id, resource_type], ...]
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
                    token_profile_row,
                    resource_row.id,
                    principal_id,
                    principal_type,
                    permission_level,
                )

        self.session.commit()

        # agg_perm_list = await self.get_aggregate_permission_list(resource_list)
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
        self,
        token_profile_row,
        resource_id,
        principal_id,
        principal_type,
        permission_level,
    ):
        # TODO: Check that token_profile_row has CHANGE permission for resource_id.
        principal_enum = db.permission.PrincipalType[principal_type.upper()]
        permission_row = self._get_permission(resource_id, principal_id, principal_enum)

        if permission_level == 0:
            if permission_row is not None:
                self.session.delete(permission_row)
        else:
            if permission_row is None:
                permission_row = db.permission.Permission(
                    resource_id=resource_id,
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

    async def get_aggregate_collection_dict(self, token_profile_row, search_str):
        """Get a list of collections with nested resources and permissions. The
         permissions are aggregated by principal, and only the highest permission level
         is returned for each principal and resource type.

        In the DB:

        - A collection contains zero to many resources
        - A resource contains zero to many permissions
        - A permission contains one profile, or one group, or one public permission

        We return:

        - A dict of collections
        - Each collection contains a dict of resource types
        - Each resource type contains a dict of resources
        - Each resource contains a dict of profiles
        - Each principal contains the max permission level found for that principal in the
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
                    db.permission.Permission.principal_type
                    == db.permission.PrincipalType.PROFILE,
                ),
            )
            .outerjoin(
                db.group.Group,
                sqlalchemy.and_(
                    db.permission.Permission.principal_id == db.group.Group.id,
                    db.permission.Permission.principal_type
                    == db.permission.PrincipalType.GROUP,
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

        # log.debug(query)

        # Dicts preserve insertion order, so the dict structure will mirror the order in
        # the order_by clause. The order will also carry over to the JSON output.

        collection_dict = {}

        for (
            collection_row,
            resource_row,
            permission_row,
            profile_row,
            group_row,
        ) in query.yield_per(Config.DB_YIELD_ROWS):
            resource_dict = collection_dict.setdefault(
                collection_row.id,
                {
                    'collection_label': collection_row.label,
                    'collection_type': collection_row.type,
                    'resource_dict': {},
                },
            )['resource_dict']

            if resource_row is None:
                continue

            permission_dict = resource_dict.setdefault(
                resource_row.type,
                {
                    'resource_id_dict': {},
                    'principal_dict': {},
                },
            )

            permission_dict['resource_id_dict'][resource_row.id] = resource_row.label

            if permission_row is None:
                continue

            principal_dict = permission_dict['principal_dict']

            if profile_row is not None:
                # Principal is a profile
                assert group_row is None, 'Profile and group cannot join on same row'
                d = {
                    'principal_id': profile_row.id,
                    'principal_type': 'profile',
                    'pasta_id': profile_row.pasta_id,
                    'title': profile_row.full_name,
                    'description': profile_row.email,
                }
            elif group_row is not None:
                # Principal is a group
                assert profile_row is None, 'Profile and group cannot join on same row'
                d = {
                    'principal_id': group_row.id,
                    'principal_type': 'group',
                    'pasta_id': group_row.pasta_id,
                    'title': group_row.name,
                    'description': group_row.description,
                }
            else:
                # Principal is the public user
                assert permission_row.principal_id is None
                d = {
                    'principal_id': None,
                    'principal_type': 'public',
                    'pasta_id': '',
                    'title': 'Public Access',
                    'description': None,
                }

            principal_info_dict = principal_dict.setdefault(
                (d['principal_id'], d['principal_type']), {**d, 'permission_level': 0}
            )

            principal_info_dict['permission_level'] = max(
                principal_info_dict['permission_level'], permission_row.level.value
            )

        # Iterate over principal_dict and convert to sorted lists
        for collection_id, collection_info_dict in collection_dict.items():
            for resource_type, resource_info_dict in collection_info_dict[
                'resource_dict'
            ].items():
                resource_info_dict['principal_list'] = sorted(
                    resource_info_dict['principal_dict'].values(),
                    key=lambda p: (
                        p['principal_type'],
                        p['title'],
                        p['description'],
                        p['principal_id'],
                    )
                    if p['principal_id'] is not None
                    else ('',),
                )
                del resource_info_dict['principal_dict']

        return collection_dict

    async def get_aggregate_permission_list(self, resource_list):
        """Get a list of aggregated maximum profiles and permissions for a list of
        resources.

        :param resource_list: [[collection_id, resource_type], ...]
        """
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
                    db.permission.Permission.principal_type
                    == db.permission.PrincipalType.PROFILE,
                ),
            )
            .outerjoin(
                db.group.Group,
                sqlalchemy.and_(
                    db.permission.Permission.principal_id == db.group.Group.id,
                    db.permission.Permission.principal_type
                    == db.permission.PrincipalType.GROUP,
                ),
            )
            .filter(
                sqlalchemy.tuple_(
                    db.permission.Collection.id,
                    db.permission.Resource.type,
                ).in_(resource_list)
            )
        )

        principal_dict = {}

        for (
            collection_row,
            resource_row,
            permission_row,
            profile_row,
            group_row,
        ) in query.yield_per(Config.DB_YIELD_ROWS):
            if profile_row is not None:
                # Principal is a profile
                assert group_row is None, 'Profile and group cannot join on same row'
                d = {
                    'principal_id': profile_row.id,
                    'principal_type': 'profile',
                    'pasta_id': profile_row.pasta_id,
                    'title': profile_row.full_name,
                    'description': profile_row.email,
                    'avatar_url': profile_row.avatar_url,
                }
            elif group_row is not None:
                # Principal is a group
                assert profile_row is None, 'Profile and group cannot join on same row'
                d = {
                    'principal_id': group_row.id,
                    'principal_type': 'group',
                    'pasta_id': group_row.pasta_id,
                    'title': group_row.name,
                    'description': (group_row.description or '')
                    + f' (Owner: {group_row.profile.full_name})'.strip(),
                    'avatar_url': str(util.avatar.get_group_avatar_url()),
                }
            else:
                # Principal is the public user
                assert permission_row.principal_id is None
                d = {
                    'principal_id': None,
                    'principal_type': 'public',
                    'pasta_id': '',
                    'title': 'PUBLIC',
                    'description': 'Public Access',
                    'avatar_url': str(util.avatar.get_public_avatar_url()),
                }

            principal_info_dict = principal_dict.setdefault(
                (d['principal_id'], d['principal_type']), {**d, 'permission_level': 0}
            )

            principal_info_dict['permission_level'] = max(
                principal_info_dict['permission_level'], permission_row.level.value
            )

        if not (None, 'public') in principal_dict:
            principal_dict[(None, 'public')] = {
                'principal_id': None,
                'principal_type': 'public',
                'pasta_id': '',
                'title': 'Public',
                'description': 'Public Access',
                'avatar_url': str(util.avatar.get_public_avatar_url()),
                'permission_level': 0,
            }

        return sorted(
            principal_dict.values(),
            key=lambda p: (
                p['principal_type'],
                p['title'],
                p['description'],
                p['principal_id'],
            )
            if p['principal_id'] is not None
            else ('',),
        )


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

