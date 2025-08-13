import uuid

import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.ext.asyncio

from db.models.permission import Resource
from db.models.search import (
    RootResource,
    PackageScope,
    ResourceType,
    SearchSession,
    SearchResult,
)

# Package scope.identifier.revision
# identifier.revision are the correct terms, though 'version' would probably be more correct
PACKAGE_RX = '^[^.]+\.[0-9]+\.[0-9]+$'

log = daiquiri.getLogger(__name__)

# noinspection PyTypeChecker,PyUnresolvedReferences
class SearchInterface:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    async def init_search_package_scopes(self):
        """Initialize the package scopes in the database.

        This table is for providing a list of package scopes that can be searched. The scopes are
        derived from the Resource labels of type 'package', which are expected to be in the format
        'scope.identifier.version'.
        """
        # Delete all existing search package scopes. Since we're in a transaction, the temporarily
        # empty table will not be visible to other transactions.
        await self._session.execute(sqlalchemy.delete(PackageScope))

        stmt = sqlalchemy.insert(PackageScope).from_select(
            ['id', 'scope'],
            sqlalchemy.select(
                sqlalchemy.func.dense_rank()
                .over(order_by=sqlalchemy.func.split_part(Resource.label, '.', 1))
                .label('id'),
                sqlalchemy.func.split_part(Resource.label, '.', 1).label('scope'),
            )
            .where(
                Resource.type == 'package',
                sqlalchemy.func.regexp_match(Resource.label, PACKAGE_RX).isnot(None),
            )
            .distinct(),
        )
        await self._session.execute(stmt)

    async def get_search_package_scopes(self):
        """Get all package scopes from the database."""
        stmt = sqlalchemy.select(PackageScope).order_by(PackageScope.scope)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def init_search_resource_types(self):
        """Initialize the non-package root resource types in the database.

        This table is for providing a list of resource types that can be searched. The resources
        must be root resources and cannot be of type 'package' since those are handled separately.
        """
        await self._session.execute(sqlalchemy.delete(ResourceType))

        # Insert new resource types based on the Resource labels, ensuring uniqueness.
        stmt = (
            sqlalchemy.insert(ResourceType)
            .from_select(
                ['id', 'type'],
                sqlalchemy.select(
                    sqlalchemy.func.dense_rank().over(order_by=Resource.type).label('id'),
                    Resource.type,
                )
                .where(
                    Resource.parent_id.is_(None),
                    # Exclude package types since we have a separate search for them.
                    Resource.type != 'package',
                )
                .distinct(),
            )
            .execution_options(synchronize_session='fetch')
        )
        await self._session.execute(stmt)

    async def get_search_resource_types(self):
        """Get all resource types that can be used in a search (see criteria in init)"""
        stmt = sqlalchemy.select(ResourceType).order_by(ResourceType.type)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def sync_search_root_resources(self):
        """Copy all root nodes from the Resource table to the RootResource table."""
        # Delete all existing root resources.
        await self._session.execute(sqlalchemy.delete(RootResource))
        # Order resources by label, with a special case for scope.id.version package identifiers.
        # Labels not matching the pattern are ordered by the full string value.
        regex_match = sqlalchemy.func.regexp_match(Resource.label, PACKAGE_RX)
        order_by_clause = [
            sqlalchemy.case(
                (regex_match.isnot(None), sqlalchemy.func.split_part(Resource.label, '.', 1)),
                else_=Resource.label,
            ),
            sqlalchemy.case(
                (
                    regex_match.isnot(None),
                    sqlalchemy.cast(
                        sqlalchemy.func.split_part(Resource.label, '.', 2), sqlalchemy.Integer
                    ),
                ),
                else_=None,
            ),
            sqlalchemy.case(
                (
                    regex_match.isnot(None),
                    sqlalchemy.cast(
                        sqlalchemy.func.split_part(Resource.label, '.', 3), sqlalchemy.Integer
                    ),
                ),
                else_=None,
            ),
        ]

        # Insert all root resources.
        stmt = (
            sqlalchemy.insert(RootResource)
            .from_select(
                ['resource_id', 'label', 'type', 'package_scope', 'package_id', 'package_rev'],
                sqlalchemy.select(
                    Resource.id,
                    Resource.label,
                    Resource.type,
                    sqlalchemy.case(
                        (
                            sqlalchemy.func.regexp_match(Resource.label, PACKAGE_RX).isnot(None),
                            sqlalchemy.func.split_part(Resource.label, '.', 1),
                        ),
                        else_=None,
                    ).label('package_scope'),
                    sqlalchemy.case(
                        (
                            sqlalchemy.func.regexp_match(Resource.label, PACKAGE_RX).isnot(None),
                            sqlalchemy.cast(
                                sqlalchemy.func.split_part(Resource.label, '.', 2),
                                sqlalchemy.Integer,
                            ),
                        ),
                        else_=None,
                    ).label('package_id'),
                    sqlalchemy.case(
                        (
                            sqlalchemy.func.regexp_match(Resource.label, PACKAGE_RX).isnot(None),
                            sqlalchemy.cast(
                                sqlalchemy.func.split_part(Resource.label, '.', 3),
                                sqlalchemy.Integer,
                            ),
                        ),
                        else_=None,
                    ).label('package_rev'),
                )
                .where(Resource.parent_id.is_(None))
                .order_by(*order_by_clause, Resource.type),
            )
            .execution_options(synchronize_session='fetch')
        )
        await self._session.execute(stmt)
        # await self._session.commit()

    async def get_root_resources(self, start_idx, limit):
        """Get a list of root resources with pagination."""
        stmt = (
            sqlalchemy.select(RootResource).order_by(RootResource.id).offset(start_idx).limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_root_count(self):
        """Get the count of root resources."""
        stmt = sqlalchemy.select(sqlalchemy.func.count(RootResource.id))
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create_search_session(
        self,
        token_profile_row,
        search_params: dict,
    ):
        """Create a new search session"""
        new_search_session = SearchSession(
            profile=token_profile_row,
            search_params=search_params,
            uuid=uuid.uuid4().hex,
        )
        self._session.add(new_search_session)
        await self.flush()
        return new_search_session

    #
    # Search session
    #

    async def get_search_session(self, search_uuid: str):
        """Get a search session by UUID"""
        stmt = sqlalchemy.select(SearchSession).where(SearchSession.uuid == search_uuid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_search_result_count(self, search_uuid: str):
        """Get the count of search results for a given search session UUID"""
        stmt = (
            sqlalchemy.select(sqlalchemy.func.count(SearchResult.id))
            .join(SearchSession, SearchResult.search_session_id == SearchSession.id)
            .where(SearchSession.uuid == search_uuid)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_search_result_slice(self, search_uuid: str, start_idx: int, limit: int):
        """Get a slice of search results for a given search session UUID"""
        stmt = (
            sqlalchemy.select(SearchResult)
            .join(SearchSession, SearchResult.search_session_id == SearchSession.id)
            .where(SearchSession.uuid == search_uuid)
            .order_by(SearchResult.sort_order)
            .offset(start_idx)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def populate_search_session(
        self,
        token_profile_row,
        search_uuid: str,
    ):
        search_session_row = await self.get_search_session(search_uuid)

        if not search_session_row:
            raise ValueError(f"Search session with UUID {search_uuid} not found.")

        if search_session_row.profile_id != token_profile_row.id:
            raise ValueError("Search session does not belong to the current user.")

        if await self._is_search_session_populated(search_session_row):
            return search_session_row

        param_dict = search_session_row.search_params
        search_type = param_dict.get('search-type')
        if search_type == 'package-search':
            return await self._populate_search_session_for_packages(search_session_row)
        elif search_type == 'general-search':
            return await self._populate_search_session_for_general_resources(search_session_row)
        else:
            raise ValueError(f"Unknown search-type: {search_type}")

    async def _populate_search_session_for_packages(
        self,
        search_session_row,
    ):
        """Populate a search session with results from a package search."""
        param_dict = search_session_row.search_params
        scope = param_dict.get('scope')
        identifier = param_dict.get('identifier')
        revision = param_dict.get('revision')

        where_conditions = []

        if scope:
            where_conditions.append(RootResource.package_scope == scope)

        where_conditions.extend(
            self._parse_range_condition(identifier, RootResource.package_id, 'identifier')
        )
        where_conditions.extend(
            self._parse_range_condition(revision, RootResource.package_rev, 'revision')
        )

        if where_conditions:
            where_clause = sqlalchemy.and_(*where_conditions)
        else:
            where_clause = sqlalchemy.true()

        return await self._populate_search_session(search_session_row, where_clause)

    async def _populate_search_session_for_general_resources(
        self,
        search_session_row,
    ):
        """Populate a search session with results from a search for general resources."""
        search_params = search_session_row.search_params
        type_str = search_params.get('type')
        label = search_params.get('label')

        where_conditions = []

        if type_str:
            where_conditions.append(RootResource.type == type_str)

        if label:
            # Translate wildcards in label to SQL wildcards.
            label = label.replace('*', '%').replace('?', '_')
            where_conditions.append(RootResource.label.like(label))

        if where_conditions:
            where_clause = sqlalchemy.and_(*where_conditions)
        else:
            where_clause = sqlalchemy.true()

        return await self._populate_search_session(search_session_row, where_clause)

    async def _is_search_session_populated(self, search_session_row):
        """Check if a search session has any results populated"""
        result = await self._session.execute(
            sqlalchemy.select(
                sqlalchemy.exists().where(SearchResult.search_session == search_session_row)
            )
        )
        return result.scalar_one()

    def _parse_range_condition(self, range_str: str, column, field_name: str):
        """Parse a range condition (e.g., '100', '100-200', '-100', '100-') and return WHERE
        conditions."""
        if range_str and range_str != '*':
            id_tup = tuple((int(v) if v else None) for v in range_str.split('-'))
            if len(id_tup) == 1:
                # Single value (e.g., '100')
                return (column == id_tup[0],)
            elif len(id_tup) == 2:
                start, end = id_tup
                if start and end:
                    # Range (e.g., '100-200')
                    return (column.between(start, end),)
                elif start:
                    # Lower bound only (e.g., '100-')
                    return (column >= start,)
                elif end:
                    # Upper bound only (e.g., '-100')
                    return (column <= end,)
            else:
                raise ValueError(f'Invalid {field_name} format: {range_str}')
        return []

    async def _populate_search_session(self, search_session_row, where_clause):
        stmt = sqlalchemy.insert(SearchResult).from_select(
            [
                'search_session_id',
                'sort_order',
                'resource_id',
                'resource_label',
                'resource_type',
            ],
            sqlalchemy.select(
                search_session_row.id,
                sqlalchemy.func.row_number()
                .over(
                    order_by=(
                        RootResource.package_scope,
                        RootResource.package_id,
                        RootResource.package_rev,
                        RootResource.label,
                        RootResource.type,
                    )
                )
                .label('sort_order'),
                RootResource.resource_id.label('resource_id'),
                RootResource.label.label('resource_label'),
                RootResource.type.label('resource_type'),
            ).where(where_clause),
        )
        await self._session.execute(stmt)
        await self.flush()
        return search_session_row
