import daiquiri
import sqlalchemy.ext.asyncio

import db.interface.util
import db.models.permission
import db.models.profile
import db.resource_tree
import util.avatar
import util.profile_cache
from config import Config

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class PermissionDb:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    async def create_resource(self, parent_id, key, label, type_str):
        """Create a new resource."""
        new_resource_row = db.models.permission.Resource(
            parent_id=parent_id,
            key=key,
            label=label,
            type=type_str,
        )
        self._session.add(new_resource_row)
        await self.flush()
        return new_resource_row

    async def update_resource(
        self, token_profile_row, key, label=None, type_str=None, parent_resource_row=None
    ):
        """Update a resource.

        The resource must have CHANGE permission for the profile, or a group of which the profile is
        a member.
        """
        resource_row = await self._get_owned_resource_by_key(token_profile_row, key)

        if label:
            resource_row.label = label
        if type_str:
            resource_row.type = type_str
        if parent_resource_row:
            result = await self.execute(
                sqlalchemy.select(db.resource_tree.get_resource_tree_for_ui(resource_row.id)).where(
                    db.resource_tree.get_resource_tree_for_ui(resource_row.id).id
                    == parent_resource_row.id
                )
            )
            if result.scalars().first():
                raise ValueError(
                    f'Cannot set parent resource: The requested parent is currently a child or '
                    f'descendant of the resource to be updated. resource_id={resource_row.id} '
                    f'parent_resource_id={parent_resource_row.id}'
                )

    async def _get_owned_resource_by_key(self, token_profile_row, key):
        """Get a resource by its key. The resource must have CHANGE permission for the profile, or a
        group of which the profile is a member.
        """
        result = await self.execute(
            sqlalchemy.select(db.models.permission.Resource).where(
                db.models.permission.Resource.key == key
            )
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
        """Set the label of a resource by its key."""
        result = await self.execute(
            sqlalchemy.select(db.models.permission.Resource).where(
                db.models.permission.Resource.key == key
            )
        )
        resource_row = result.scalars().first()
        if resource_row is None:
            raise ValueError(f'Resource {key} not found')
        resource_row.label = label

    async def _remove_resource_by_key(self, key):
        """Remove a resource by its key."""
        result = await self.execute(
            sqlalchemy.select(db.models.permission.Resource).where(
                db.models.permission.Resource.key == key
            )
        )
        resource_row = result.scalars().first()
        if resource_row is None:
            raise ValueError(f'Resource {key} not found')
        await self._session.delete(resource_row)

    async def get_resource_types(self, token_profile_row):
        """Get a list of resource types that the profile has CHANGE permission on."""
        result = await self.execute(
            (
                sqlalchemy.select(db.models.permission.Resource.type)
                .join(
                    db.models.permission.Rule,
                    db.models.permission.Rule.resource_id == db.models.permission.Resource.id,
                )
                .join(
                    db.models.permission.Principal,
                    db.models.permission.Principal.id == db.models.permission.Rule.principal_id,
                )
                .where(
                    db.models.permission.Principal.subject_id == token_profile_row.id,
                    db.models.permission.Principal.subject_type
                    == db.models.permission.SubjectType.PROFILE,
                    db.models.permission.Rule.permission
                    >= db.models.permission.PermissionLevel.CHANGE,
                )
                .order_by(db.models.permission.Resource.type)
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

        permission_level = db.models.permission.permission_level_int_to_enum(permission_level)

        parent_id_set = set()

        # Recursively find all parent IDs of the resources in resource_ids.

        async def _find_parent_ids(resource_id):
            """Recursively find all parent IDs of the given resource ID."""
            result = await self.execute(
                sqlalchemy.select(db.models.permission.Resource.parent_id).where(
                    db.models.permission.Resource.id == resource_id
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
                result = await self.execute(
                    (
                        sqlalchemy.select(db.models.permission.Resource.id)
                        .join(
                            db.models.permission.Rule,
                            db.models.permission.Rule.resource_id
                            == db.models.permission.Resource.id,
                        )
                        .join(
                            db.models.permission.Principal,
                            db.models.permission.Principal.id
                            == db.models.permission.Rule.principal_id,
                        )
                        .where(
                            # db.models.permission.Resource.id.in_(resource_chunk_list),
                            db.models.permission.Principal.subject_id == token_profile_row.id,
                            db.models.permission.Principal.subject_type
                            == db.models.permission.SubjectType.PROFILE,
                            db.models.permission.Rule.permission
                            >= db.models.permission.PermissionLevel.CHANGE,
                        )
                    )
                )
                change_resource_id_set = {row for row, in result.all()}

                change_resource_id_set = set(resource_chunk_list)

            log.debug(f'change_resource_id_set: {change_resource_id_set}')
            # If permission is NONE, all we need to do is delete any existing permission rows for
            # the principal on the given resources.
            if permission_level == db.models.permission.PermissionLevel.NONE:
                delete_stmt = sqlalchemy.delete(db.models.permission.Rule).where(
                    db.models.permission.Rule.resource_id.in_(change_resource_id_set),
                    db.models.permission.Rule.principal_id == principal_id,
                )
                await self.execute(delete_stmt)
                return
            # Create a set of secure resource IDs for which there are no existing permission rows
            # for the principal.
            # We start by creating a subquery which returns the resource IDs for which the principal
            # already has a permission row.
            result = await self.execute(
                sqlalchemy.select(db.models.permission.Resource.id).where(
                    db.models.permission.Resource.id.in_(change_resource_id_set),
                    ~db.models.permission.Resource.id.in_(
                        (
                            sqlalchemy.select(db.models.permission.Resource.id)
                            .join(db.models.permission.Rule)
                            .where(
                                db.models.permission.Resource.id.in_(change_resource_id_set),
                                db.models.permission.Rule.principal_id == principal_id,
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
                    sqlalchemy.insert(db.models.permission.Rule),
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
                    sqlalchemy.update(db.models.permission.Rule)
                    .where(
                        db.models.permission.Rule.resource_id.in_(update_resource_id_set),
                        db.models.permission.Rule.principal_id == principal_id,
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
    #             await self._create_or_update_permission(
    #                 resource_row.id,
    #                 principal_id,
    #                 principal_type,
    #                 permission_level,
    #             )

    async def _create_or_update_permission(
        self,
        resource_row,
        principal_row,
        permission_level,
    ):
        """Create or update a permission for a principal on a resource.

        CHANGE permission on the resource must already have been validated before calling this
        method.
        """
        rule_row = await self._get_rule(resource_row, principal_row)

        if permission_level == 0:
            if rule_row is not None:
                await self._session.delete(rule_row)
        else:
            if rule_row is None:
                # principal_row = self.get_principal_by_subject(principal_row, principal_type)
                rule_row = db.models.permission.Rule(
                    resource=resource_row,
                    principal=principal_row,
                    permission=db.models.permission.PermissionLevel(permission_level),
                )
                self._session.add(rule_row)
            else:
                rule_row.permission = db.models.permission.PermissionLevel(permission_level)

    async def _get_rule(self, resource_row, principal_row):
        # The db.models.permission.Rule table has a unique constraint on (resource_id, principal_id), so there will be 0
        # or 1 match to this query.
        result = await self.execute(
            (
                sqlalchemy.select(db.models.permission.Rule)
                .join(
                    db.models.permission.Principal,
                    db.models.permission.Principal.id == db.models.permission.Rule.principal_id,
                )
                .where(
                    db.models.permission.Rule.resource == resource_row,
                    db.models.permission.Principal == principal_row,
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
        token_has_change_permission_subquery = (
            sqlalchemy.select(db.models.permission.Resource.id)
            .join(db.models.permission.Rule)
            .join(
                db.models.permission.Principal,
                db.models.permission.Principal.id == db.models.permission.Rule.principal_id,
            )
            .where(
                db.models.permission.Principal.subject_id == token_profile_row.id,
                db.models.permission.Principal.subject_type
                == db.models.permission.SubjectType.PROFILE,
                db.models.permission.Rule.permission == db.models.permission.PermissionLevel.CHANGE,
            )
        )

        # Main query to fetch resources, rules and principals
        stmt = (
            sqlalchemy.select(
                db.models.permission.Resource,
                db.models.permission.Rule,
                db.models.permission.Principal,
                db.models.profile.Profile,
                db.models.group.Group,
            )
            .select_from(db.models.permission.Resource)
            # In SQLAlchemy, outerjoin() is a left join. Right join is not directly supported (have
            # to swap the order of the tables).
            .join(
                db.models.permission.Rule,
                db.models.permission.Rule.resource_id == db.models.permission.Resource.id,
            )
            .join(
                db.models.permission.Principal,
                db.models.permission.Principal.id == db.models.permission.Rule.principal_id,
            )
            .outerjoin(
                db.models.profile.Profile,
                sqlalchemy.and_(
                    db.models.profile.Profile.id == db.models.permission.Principal.subject_id,
                    db.models.permission.Principal.subject_type
                    == db.models.permission.SubjectType.PROFILE,
                ),
            )
            .outerjoin(
                db.models.group.Group,
                sqlalchemy.and_(
                    db.models.group.Group.id == db.models.permission.Principal.subject_id,
                    db.models.permission.Principal.subject_type
                    == db.models.permission.SubjectType.GROUP,
                ),
            )
        )

        if not util.profile_cache.is_superuser(token_profile_row):
            stmt = stmt.where(
                db.models.permission.Resource.label.ilike(f'{search_str}%'),
                db.models.permission.Resource.id.in_(token_has_change_permission_subquery),
            )

        # Filter by resource type if provided.
        # A statement can have multiple WHERE clauses, which will be combined with AND by
        # SQLAlchemy.
        if resource_type is not None:
            stmt = stmt.where(db.models.permission.Resource.type == resource_type)

        # Add ordering to the query
        stmt = stmt.order_by(
            db.models.permission.Resource.type,
            db.models.permission.Resource.label,
            db.models.profile.Profile.common_name,
            db.models.profile.Profile.email,
        )

        result = await self.execute(stmt)
        return result.all()

    async def get_resource_parents(self, token_profile_row, resource_ids):
        """Get the parent resources for a list of resource IDs."""
        # result = await self.execute(sqlalchemy.text('select * from get_resource_parents')
        stmt = select(func.get_resource_parents(node_ids))
        result = await session.execute(stmt)
        return result.fetchall()

    async def get_permission_generator(self, resource_ids):
        """Yield profiles and permissions for a list of resources."""
        for i in range(0, len(resource_ids), Config.DB_CHUNK_SIZE):
            resource_chunk_list = resource_ids[i : i + Config.DB_CHUNK_SIZE]

            stmt = (
                sqlalchemy.select(
                    db.models.permission.Resource,
                    db.models.permission.Rule,
                    db.models.permission.Principal,
                    db.models.profile.Profile,
                    db.models.group.Group,
                )
                .select_from(db.models.permission.Resource)
                .join(
                    db.models.permission.Rule,
                    db.models.permission.Rule.resource_id == db.models.permission.Resource.id,
                )
                .join(
                    db.models.permission.Principal,
                    db.models.permission.Principal.id == db.models.permission.Rule.principal_id,
                )
                .outerjoin(
                    db.models.profile.Profile,
                    sqlalchemy.and_(
                        db.models.profile.Profile.id == db.models.permission.Principal.subject_id,
                        db.models.permission.Principal.subject_type
                        == db.models.permission.SubjectType.PROFILE,
                    ),
                )
                .outerjoin(
                    db.models.group.Group,
                    sqlalchemy.and_(
                        db.models.group.Group.id == db.models.permission.Principal.subject_id,
                        db.models.permission.Principal.subject_type
                        == db.models.permission.SubjectType.GROUP,
                    ),
                )
                .where(db.models.permission.Resource.id.in_(resource_chunk_list))
            )
            result = await self._session.stream(stmt)
            # async for row in result.scalars():
            async for row in result:
                yield row
