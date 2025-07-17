"""Permission interface for managing resources and permissions in the database.

Some terms:

    - Resource: An object that can have permissions associated with it
    - Principal: An entity (currently a Profile or a Group) that can be granted access to a resource
    - Profile: A principal which holds user profile information
    - Group: A principal which holds a group of profiles
    - Rule / Permission: An access control rule that grants access to a principal for a resource at
        a certain level (READ, WRITE, CHANGE).
    - Permission Level: The level of access granted by a permission (READ, WRITE, CHANGE).
    
The resources of interest will always be a cross-section of:

    - a set of resources (e.g., a single resource, resources in the same tree, or found in a search)
    - a set of equivalent principals
    - a set of rules which tie the resources and principals together,
      where only rules having higher or equal permission level to that requested, are considered

    The queries are lengthy in source code, because, well, SQLAlchemy. But we're essentially
    working just with variations around this basic query:

        select * from resource
        join rule on rule.resource_id = resource.id
        where rule.level >= requested_level
        and rule.principal in (subquery to select all equivalent principals)

    To this, we add filters, and if we need more information about the principals, we join
    on profile and/or group tables.

    We expect the list of equivalent principals to be short. Usually just the public subject, the
    authorized subject, and maybe a couple of group memberships. Still, the DB should be able to
    handle thousands of equivalent principals efficiently, should someone want that in the future.
"""
import re

import daiquiri
import sqlalchemy.ext.asyncio

import db.interface.util
from db.models.permission import (
    permission_level_int_to_enum,
    SubjectType,
    Resource,
    Rule,
    PermissionLevel,
    Principal,
)
from db.models.profile import Profile
import db.resource_tree
import util.avatar
import util.profile_cache
from config import Config

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class PermissionInterface:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    async def create_resource(self, parent_id, key, label, type_str):
        """Create a new resource."""
        new_resource_row = Resource(
            parent_id=parent_id,
            key=key,
            label=label,
            type=type_str,
        )
        self._session.add(new_resource_row)
        await self.flush()
        return new_resource_row

    async def get_resource(self, key):
        """Get a resource by its key."""
        result = await self.execute(
            sqlalchemy.select(Resource)
            .options(sqlalchemy.orm.selectinload(Resource.parent))
            .where(Resource.key == key)
        )
        return result.scalar()

    async def update_resource(
        self, token_profile_row, key, parent_resource_key=None, label=None, type_str=None
    ):
        """Update a resource.

        - To update the label and/or type, the profile must have WRITE on the resource being
        updated.
        - To change the parent resource, the profile must have WRITE on both the resource being
        updated, and the parent resource. No information is updated in the parent, but we consider
        adding a child to be a change to the parent.
        - To add or remove ACRs on the resource, the profile must have CHANGE permission on the
        resource. (Not handled by this method. See the Rules API).
        """
        resource_row = await self.get_resource(key)
        assert resource_row is not None, f'Attempt to update non-existing resource: "{key}"'

        if not await self.is_authorized(token_profile_row, resource_row, PermissionLevel.WRITE):
            raise ValueError(
                f'Profile "{token_profile_row.edi_id}" does not have WRITE permission on '
                f'resource "{key}"'
            )

        if parent_resource_key:
            # Check permission on the new parent resource.
            parent_resource_row = await self.get_resource(parent_resource_key)
            if not await self.is_authorized(
                token_profile_row, parent_resource_row, PermissionLevel.WRITE
            ):
                raise ValueError(
                    f'Profile "{token_profile_row.edi_id}" does not have WRITE permission on '
                    f'parent resource "{parent_resource_row.key}"'
                )
            # Check that the new parent is not a descendant of the resource being updated, which
            # would create a cycle in the graph.
            descendant_id_list = self.get_resource_descendants_id_set([resource_row.id])
            if parent_resource_row.id in descendant_id_list:
                raise ValueError(
                    f'Cannot set parent resource: The requested parent is currently a descendant '
                    f'of the resource to be updated. resource_key={resource_row.key} '
                    f'parent_resource_key={parent_resource_row.key}'
                )
            # Parent is ok, so we can set it.

        if label:
            resource_row.label = label
        if type_str:
            resource_row.type = type_str

    async def get_owned_resource_by_key(self, token_profile_row, key):
        """Get a resource by its key. The resource must have CHANGE permission for the profile, or a
        group of which the profile is a member.

        :returns:
            The resource row if found, or None if the resource does not exist or is not owned by the
            profile.
        """

        if resource_row is None:
            return None

        if not self.is_authorized(token_profile_row, resource_row, PermissionLevel.CHANGE):
            raise ValueError(
                f'Profile {token_profile_row.id} does not have CHANGE permission on resource {key}'
            )

        return result.scalar()

    async def is_authorized(self, token_profile_row, resource_row, permission_level):
        """Check if a profile has a specific permission or higher on a resource.

        This method implements the logic equivalent of the following pseudocode:

        def is_authorized(principal, resource, permission_level):
            acl = getAcl(resource)
            principals = getPrincipals(profile)
            for principal in principals:
                for acr in acl:
                    if acr.principal == principal:
                        if acr.permission_level >= permission_level:
                            return True
            return False

        A profile may have a number of equivalents. These always include the Public Access profile,
        and may include one or more groups to which profile is a member. This method checks if the
        profile, or any of its equivalents, has the required permission or better on the resource.

        E.g., if the token profile has no permissions on the resource, but is a member of a group
        that has WRITE permission on the resource, this method will return True when checking for
        either READ or WRITE on the resource
        """
        result = await self.execute(
            sqlalchemy.select(
                sqlalchemy.exists().where(
                    Rule.resource == resource_row,
                    Rule.principal_id.in_(
                        await self._get_equivalent_principal_id_query(token_profile_row)
                    ),
                    Rule.permission >= permission_level,
                )
            )
        )
        return result.scalar()

    # async def get_resource_list_by_key(self, key, include_ancestors=False, include_descendants=False):
    #     """Get a list of resources by their key.
    #
    #     If include_ancestors is True, the chain of the resource's ancestors (up to the root), will be
    #     included in the result.
    #
    #     If include_descendants is True, all the resource's descendants will be included in the result.
    #     """
    #     stmt = sqlalchemy.select(db.models.permission.Resource).where(
    #         db.models.permission.Resource.key == key
    #     )
    #     # if include_ancestors or include_descendants:
    #     #     stmt = db.resource_tree.get_resource_tree_for_ui(
    #     #         db.models.permission.Resource.id,
    #     #         include_ancestors=include_ancestors,
    #     #         include_descendants=include_descendants,
    #     #     ).where(db.models.permission.Resource.key == key)
    #     result = await self.execute(stmt)
    #     return result.scalars().all()

    async def get_all_resource_keys(self):
        """Get all resource keys."""
        result = await self.execute(sqlalchemy.select(Resource.key).order_by(Resource.key))
        return result.scalars().all()

    async def _set_resource_label_by_key(self, key, label):
        """Set the label of a resource by its key."""
        result = await self.execute(sqlalchemy.select(Resource).where(Resource.key == key))
        resource_row = result.scalar()
        if resource_row is None:
            raise ValueError(f'Resource {key} not found')
        resource_row.label = label

    async def _remove_resource_by_key(self, key):
        """Remove a resource by its key."""
        result = await self.execute(sqlalchemy.select(Resource).where(Resource.key == key))
        resource_row = result.scalar()
        if resource_row is None:
            raise ValueError(f'Resource {key} not found')
        await self._session.delete(resource_row)

    async def get_resource_types(self, token_profile_row):
        """Get a list of resource types that the profile has CHANGE permission on."""
        result = await self.execute(
            (
                sqlalchemy.select(Resource.type)
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
                    Rule.permission >= PermissionLevel.CHANGE,
                )
                .order_by(Resource.type)
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

        permission_level = permission_level_int_to_enum(permission_level)

        parent_id_set = set()

        # Recursively find all parent IDs of the resources in resource_ids.

        async def _find_parent_ids(resource_id):
            """Recursively find all parent IDs of the given resource ID."""
            result = await self.execute(
                sqlalchemy.select(Resource.parent_id).where(Resource.id == resource_id)
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
                result = await self.execute(
                    (
                        sqlalchemy.select(Resource.id)
                        .join(
                            Rule,
                            Rule.resource_id == Resource.id,
                        )
                        .join(
                            Principal,
                            Principal.id == Rule.principal_id,
                        )
                        .where(
                            # db.models.permission.Resource.id.in_(resource_chunk_list),
                            Principal.subject_id == token_profile_row.id,
                            Principal.subject_type == SubjectType.PROFILE,
                            Rule.permission >= PermissionLevel.CHANGE,
                        )
                    )
                )
                change_resource_id_set = {row for row, in result.all()}

                change_resource_id_set = set(resource_chunk_list)

            log.debug(f'change_resource_id_set: {change_resource_id_set}')
            # If permission is NONE, all we need to do is delete any existing permission rows for
            # the principal on the given resources.
            if permission_level == PermissionLevel.NONE:
                delete_stmt = sqlalchemy.delete(Rule).where(
                    Rule.resource_id.in_(change_resource_id_set),
                    Rule.principal_id == principal_id,
                )
                await self.execute(delete_stmt)
                return
            # Create a set of secure resource IDs for which there are no existing permission rows
            # for the principal.
            # We start by creating a subquery which returns the resource IDs for which the principal
            # already has a permission row.
            result = await self.execute(
                sqlalchemy.select(Resource.id).where(
                    Resource.id.in_(change_resource_id_set),
                    ~Resource.id.in_(
                        (
                            sqlalchemy.select(Resource.id)
                            .join(Rule)
                            .where(
                                Resource.id.in_(change_resource_id_set),
                                Rule.principal_id == principal_id,
                            )
                        )
                    ),
                )
            )
            # Insert any absent permission rows for the principal.
            insert_resource_id_set = {row for row, in result.all()}
            log.debug(f'insert_resource_id_set: {insert_resource_id_set}')
            if insert_resource_id_set:
                await self.execute(
                    sqlalchemy.insert(Rule),
                    [
                        {
                            'resource_id': resource_id,
                            'principal_id': principal_id,
                            'permission': permission_level,
                        }
                        for resource_id in insert_resource_id_set
                    ],
                )
            # Update any existing permission rows for the principal.
            update_resource_id_set = change_resource_id_set - insert_resource_id_set
            log.debug(f'update_resource_id_set: {update_resource_id_set}')
            if update_resource_id_set:
                update_stmt = (
                    sqlalchemy.update(Rule)
                    .where(
                        Rule.resource_id.in_(update_resource_id_set),
                        Rule.principal_id == principal_id,
                    )
                    .values(permission=permission_level)
                )
                await self.execute(update_stmt)

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
    #             await self._session.query(db.models.permission.Resource)
    #             .filter(
    #                 db.models.permission.Resource.parent_id == parent_id,
    #                 db.models.permission.Resource.type == resource_type,
    #             )
    #             .all()
    #         )
    #         for resource_row in resource_row_query:
    #             await self._create_or_update_rule(
    #                 resource_row.id,
    #                 principal_id,
    #                 principal_type,
    #                 permission_level,
    #             )

    async def create_or_update_rule(
        self,
        resource_row,
        principal_row,
        permission_level,
    ):
        """Create or update a permission for a principal on a resource.

        CHANGE permission on the resource must already have been validated before calling this
        method.
        """
        assert isinstance(resource_row, Resource)
        assert isinstance(principal_row, Principal)
        assert isinstance(permission_level, PermissionLevel)

        rule_row = await self.get_rule(resource_row, principal_row)

        if permission_level == 0:
            if rule_row is not None:
                await self._session.delete(rule_row)
        else:
            if rule_row is None:
                rule_row = Rule(
                    resource=resource_row,
                    principal=principal_row,
                    permission=permission_level,
                )
                self._session.add(rule_row)
            else:
                rule_row.permission = permission_level

        await self.flush()

    async def get_rule(self, resource_row, principal_row):
        # The db.models.permission.Rule table has a unique constraint on (resource_id,
        # principal_id), so there will be 0 or 1 match to this query.
        result = await self.execute(
            (
                sqlalchemy.select(Rule).where(
                    Rule.resource_id == resource_row.id,
                    Rule.principal_id == principal_row.id,
                )
            )
        )
        return result.scalar()

    async def get_resource_list(self, token_profile_row, search_str, resource_type):
        """Get a list of resources and permissions, with resource labels filtered on search_str.

        if search_str is False (None or ''), return all resources.

        - A resource contains zero to many permissions
        - A resource may have a parent resource
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
        token_has_change_permission_subquery = (
            sqlalchemy.select(Resource.id)
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
                Rule.permission == PermissionLevel.CHANGE,
            )
        )

        # Main query to fetch resources, rules and principals
        stmt = (
            sqlalchemy.select(
                Resource,
                Rule,
                Principal,
                Profile,
                db.models.group.Group,
            )
            .select_from(Resource)
            .join(
                Rule,
                Rule.resource_id == Resource.id,
            )
            .join(
                Principal,
                Principal.id == Rule.principal_id,
            )
            # In SQLAlchemy, outerjoin() is a left join. Right join is not directly supported (have
            # to swap the order of the tables).
            .outerjoin(
                Profile,
                sqlalchemy.and_(
                    Profile.id == Principal.subject_id,
                    Principal.subject_type == SubjectType.PROFILE,
                ),
            )
            .outerjoin(
                db.models.group.Group,
                sqlalchemy.and_(
                    db.models.group.Group.id == Principal.subject_id,
                    Principal.subject_type == SubjectType.GROUP,
                ),
            )
            .where(
                sqlalchemy.or_(
                    sqlalchemy.and_(
                        Resource.parent_id.is_(None),
                        Resource.label.ilike(f'{search_str}%'),
                    ),
                    ~Resource.parent_id.is_(None),
                )
            )
        )

        if not util.profile_cache.is_superuser(token_profile_row):
            stmt = stmt.where(
                Resource.id.in_(token_has_change_permission_subquery),
            )

        # Filter by resource type if provided.
        # A statement can have multiple WHERE clauses, which will be combined with AND by
        # SQLAlchemy.
        if resource_type is not None:
            stmt = stmt.where(Resource.type == resource_type)

        # Add ordering to the query
        stmt = stmt.order_by(
            Resource.type,
            Resource.label,
            Profile.common_name,
            Profile.email,
        )

        result = await self.execute(stmt)
        return result.all()

    async def get_resource_ancestors_id_set(self, resource_ids):
        """Get the parent resources for a list of resource IDs."""
        stmt = sqlalchemy.select(sqlalchemy.func.get_resource_ancestors(list(resource_ids)))
        result = await self.execute(stmt)
        # db.models.permission.Resource(id=int(row[0]), label=row[1], type=row[2], parent_id=row[3])
        return {int(row[0]) for row in result.scalars()}

    async def get_resource_descendants_id_set(self, resource_ids):
        """Get the resource tree starting from a given root resource ID for a list of resource IDs."""
        stmt = sqlalchemy.select(sqlalchemy.func.get_resource_descendants(list(resource_ids)))
        result = await self.execute(stmt)
        # db.models.permission.Resource(id=row[0], label=row[1], type=row[2], parent_id=row[3])
        return {int(row[0]) for row in result.scalars()}

    # async def get_resource_generator(self, token_resource_row, resource_ids, permission_level):
    #     """Yield resources with associated ACRs for a list of resources."""
    #     for i in range(0, len(resource_ids), Config.DB_CHUNK_SIZE):
    #         resource_chunk_list = resource_ids[i : i + Config.DB_CHUNK_SIZE]
    #
    #         stmt = (
    #             sqlalchemy.select(
    #                 Resource,
    #                 Rule,
    #                 Principal,
    #                 db.models.profile.Profile,
    #                 db.models.group.Group,
    #             )
    #             .select_from(Resource)
    #             .join(
    #                 Rule,
    #                 Rule.resource_id == Resource.id,
    #             )
    #             .join(
    #                 Principal,
    #                 Principal.id == Rule.principal_id,
    #             )
    #             .outerjoin(
    #                 db.models.profile.Profile,
    #                 sqlalchemy.and_(
    #                     db.models.profile.Profile.id == Principal.subject_id,
    #                     Principal.subject_type == SubjectType.PROFILE,
    #                 ),
    #             )
    #             .outerjoin(
    #                 db.models.group.Group,
    #                 sqlalchemy.and_(
    #                     db.models.group.Group.id == Principal.subject_id,
    #                     Principal.subject_type == SubjectType.GROUP,
    #                 ),
    #             )
    #             .where(
    #                 Resource.id.in_(resource_chunk_list),
    #                 sqlalchemy.or_(
    #                     util.profile_cache.is_superuser(token_resource_row),
    #                     sqlalchemy.and_(
    #                         Rule.permission >= permission_level,
    #                         Principal.id.in_(
    #                             await self._get_equivalent_principal_id_query(token_resource_row),
    #                         ),
    #                     ),
    #                 ),
    #             )
    #         )
    #         result = await self._session.stream(stmt)
    #         # async for row in result.scalars():
    #         async for row in result.yield_per(Config.DB_YIELD_ROWS):
    #             yield row

    async def get_resource_generator(self, token_resource_row, resource_ids, permission_level):
        """Yield resources with associated ACRs for a list of resource IDs.

        Only resources for which the token_resource_row has the required permission level or higher
        will be returned.

        This method handles untrusted user input, so it is safe to use with user-provided resource
        IDs. Any resource IDs for which the token_resource_row does not have the required permission
        level or higher, or which does not exist, will be silently ignored.
        """

        # Normally, there will be no duplicated resource IDs in the list, but we dedup here just in
        # case.
        resource_ids = list(set(resource_ids))

        is_superuser = util.profile_cache.is_superuser(token_resource_row)
        equivalent_principal_id_list = (
            (await self.execute(await self._get_equivalent_principal_id_query(token_resource_row)))
            .scalars()
            .all()
        )

        for i in range(0, len(resource_ids), Config.DB_CHUNK_SIZE):
            resource_id_chunk_list = resource_ids[i : i + Config.DB_CHUNK_SIZE]

            # Filter the resource IDs to only include those for which the token_resource_row has the
            # required permission level or higher. For superusers, all resource IDs are
            # included.
            filter_subquery = (
                sqlalchemy.select(Resource.id)
                .join(
                    Rule,
                    Rule.resource_id == Resource.id,
                )
                .where(
                    Resource.id.in_(resource_id_chunk_list),
                    sqlalchemy.or_(
                        is_superuser,
                        sqlalchemy.and_(
                            Rule.permission >= permission_level,
                            # Principal.id.in_(equivalent_principal_id_list),
                            Rule.principal_id.in_(equivalent_principal_id_list),
                        ),
                    ),
                )
            ).subquery()

            stmt = (
                sqlalchemy.select(
                    Resource,
                    Rule,
                    Principal,
                    Profile,
                    db.models.group.Group,
                )
                .select_from(Resource)
                .join(
                    filter_subquery,
                    filter_subquery.c.id == Resource.id,
                )
                .join(
                    Rule,
                    Rule.resource_id == Resource.id,
                )
                .join(
                    Principal,
                    Principal.id == Rule.principal_id,
                )
                .outerjoin(
                    Profile,
                    sqlalchemy.and_(
                        Profile.id == Principal.subject_id,
                        Principal.subject_type == SubjectType.PROFILE,
                    ),
                )
                .outerjoin(
                    db.models.group.Group,
                    sqlalchemy.and_(
                        db.models.group.Group.id == Principal.subject_id,
                        Principal.subject_type == SubjectType.GROUP,
                    ),
                )
            )

            result = await self._session.stream(stmt)
            async for row in result.yield_per(Config.DB_YIELD_ROWS):
                yield row

    #
    # Principal
    #

    async def _get_equivalent_principal_id_query(self, token_profile_row):
        """Return a query that returns the principal IDs for all principals that the profile has
        access to. We refer to these as the profile's equivalent principals. These principals,
        except for the profile itself, are included in the 'principals' field of the JWT.

        The returned list includes the principal IDs of:
            - The profile itself
            - All groups in which this profile is a member
            - the Public Access profile
            - the Authenticated Access profile

        :returns: Query object for use in SQLAlchemy 'where' and 'in' clauses for rules.
        """
        public_profile_id = await util.profile_cache.get_public_access_profile_id(self)
        authenticated_profile_id = await util.profile_cache.get_authenticated_access_profile_id(
            self
        )
        # This method supports regular profiles, and should not be called for the public
        # or authenticated profiles, as they do not have any equivalent principals.
        assert token_profile_row.id not in (
            public_profile_id,
            authenticated_profile_id,
        ), 'This method should not be called for the public or authenticated profiles.'
        return (
            sqlalchemy.select(Principal.id)
            .outerjoin(
                Profile,
                sqlalchemy.and_(
                    Profile.id == Principal.subject_id,
                    Principal.subject_type == SubjectType.PROFILE,
                ),
            )
            .outerjoin(
                db.models.group.Group,
                sqlalchemy.and_(
                    db.models.group.Group.id == Principal.subject_id,
                    Principal.subject_type == SubjectType.GROUP,
                ),
            )
            .outerjoin(
                db.models.group.GroupMember,
                sqlalchemy.and_(
                    db.models.group.GroupMember.group_id == db.models.group.Group.id,
                    db.models.group.GroupMember.profile_id == token_profile_row.id,
                ),
            )
            .where(
                sqlalchemy.or_(
                    # db.models.permission.Principal ID of the db.models.profile.Profile
                    sqlalchemy.and_(
                        Principal.subject_id == token_profile_row.id,
                        Principal.subject_type == SubjectType.PROFILE,
                    ),
                    # Public Access
                    sqlalchemy.and_(
                        Principal.subject_id == public_profile_id,
                        Principal.subject_type == SubjectType.PROFILE,
                    ),
                    # Authenticated access
                    sqlalchemy.and_(
                        Principal.subject_id == authenticated_profile_id,
                        Principal.subject_type == SubjectType.PROFILE,
                    ),
                    # Groups in which the profile is a member
                    db.models.group.GroupMember.profile_id == token_profile_row.id,
                )
            )
        )

    async def get_equivalent_principal_edi_id_set(self, token_profile_row):
        """Get a set of EDI-IDs for all principals that the profile has access to.

        Note: This includes the EDI-ID for the profile itself, which should not be included in
        the 'principals' field of the JWT.
        """
        # Build the subquery for equivalent principal IDs
        principal_id_subquery = await self._get_equivalent_principal_id_query(token_profile_row)

        stmt = (
            sqlalchemy.select(
                sqlalchemy.case(
                    (
                        Principal.subject_type == SubjectType.GROUP,
                        db.models.group.Group.edi_id,
                    ),
                    else_=Profile.edi_id,
                )
            )
            .select_from(Principal)
            .outerjoin(
                db.models.group.Group,
                sqlalchemy.and_(
                    db.models.group.Group.id == Principal.subject_id,
                    Principal.subject_type == SubjectType.GROUP,
                ),
            )
            .outerjoin(
                Profile,
                sqlalchemy.and_(
                    Profile.id == Principal.subject_id,
                    Principal.subject_type == SubjectType.PROFILE,
                ),
            )
            .where(Principal.id.in_(principal_id_subquery))
        )

        return set((await self.execute(stmt)).scalars().all())

    async def _add_principal(self, subject_id, subject_type):
        """Insert a principal into the database.

        subject_id and subject_type are unique together.
        """
        new_principal_row = Principal(subject_id=subject_id, subject_type=subject_type)
        self._session.add(new_principal_row)
        await self.flush()
        return new_principal_row

    async def get_principal(self, principal_id):
        """Get a principal by its ID."""
        result = await self.execute(
            sqlalchemy.select(Principal).where(Principal.id == principal_id)
        )
        return result.scalar()

    async def get_principal_by_subject(self, subject_id, subject_type):
        """Get a principal by its entity ID and type."""
        result = await self.execute(
            sqlalchemy.select(Principal).where(
                Principal.subject_id == subject_id,
                Principal.subject_type == subject_type,
            )
        )
        return result.scalar()

    async def get_principal_by_profile(self, profile_row):
        """Get the principal for a profile."""
        result = await self.execute(
            sqlalchemy.select(Principal).where(
                Principal.subject_id == profile_row.id,
                Principal.subject_type == SubjectType.PROFILE,
            )
        )
        return result.scalar()

    async def get_principal_by_edi_id(self, edi_id):
        """Get a principal by its EDI-ID.
        The EDI-ID can be for a profile or group.
        """
        result = await self.execute(
            sqlalchemy.select(Principal)
            .outerjoin(
                Profile,
                sqlalchemy.and_(
                    Profile.id == Principal.subject_id,
                    Principal.subject_type == SubjectType.PROFILE,
                ),
            )
            .outerjoin(
                db.models.group.Group,
                sqlalchemy.and_(
                    db.models.group.Group.id == Principal.subject_id,
                    Principal.subject_type == SubjectType.GROUP,
                ),
            )
            .where(
                sqlalchemy.or_(
                    Profile.edi_id == edi_id,
                    db.models.group.Group.edi_id == edi_id,
                )
            )
        )
        return result.scalar()
