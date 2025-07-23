import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio

from db.models.permission import Resource
from db.models.tree import (
    PackageScope,
    RootResource,
    ResourceType,
)

PACKAGE_RX = '^[^.,]+\.[0-9]+\.[0-9]+$'

log = daiquiri.getLogger(__name__)

# noinspection PyTypeChecker,PyUnresolvedReferences
class TreeInterface:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    #
    #
    #

    async def update_package_scopes(self):
        """Update the package scopes in the database."""
        # Delete all existing package scopes.
        await self._session.execute(sqlalchemy.delete(PackageScope))

        # Insert new package scopes based on the Resource labels, ensuring uniqueness.
        stmt = sqlalchemy.insert(PackageScope).from_select(
            ['id', 'scope'],  # Match the target columns
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
            .distinct(),  # Ensure only unique rows are selected
        )
        await self._session.execute(stmt)

    async def get_package_scopes(self):
        """Get all package scopes from the database."""
        stmt = sqlalchemy.select(PackageScope).order_by(PackageScope.scope)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    #
    #
    #

    async def update_resource_types(self):
        """Update the resource types in the database."""
        # Delete all existing resource types.
        await self._session.execute(sqlalchemy.delete(ResourceType))

        # Insert new resource types based on the Resource labels, ensuring uniqueness.
        stmt = (
            sqlalchemy.insert(ResourceType)
            .from_select(
                ['id', 'type'],
                sqlalchemy.select(
                    sqlalchemy.func.dense_rank().over(order_by=Resource.type).label('id'),
                    Resource.type,
                ).distinct(),
            )
            .execution_options(synchronize_session='fetch')
        )
        await self._session.execute(stmt)

    async def get_resource_types(self):
        """Get all resource types from the database."""
        stmt = sqlalchemy.select(ResourceType).order_by(ResourceType.type)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    #
    #
    #

    async def update_tree(self):
        """Copy all root nodes from the Resource table to the RootResource table."""
        # Delete all existing root resources.
        await self._session.execute(sqlalchemy.delete(RootResource))
        await self._session.execute(sqlalchemy.text('alter sequence root_id_seq restart with 1'))

        # Order resources by label, with a special case for scope.id.version package identifiers.
        # Labels not matching the pattern are ordered by the full string value.

        # After
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

        # order_by_clause = [
        #     sqlalchemy.case(
        #         (
        #             sqlalchemy.func.regexp_match(Resource.label, PACKAGE_RX) != None,
        #             sqlalchemy.func.split_part(Resource.label, '.', 1),
        #         ),
        #         else_=Resource.label,
        #     ),
        #     sqlalchemy.case(
        #         (
        #             sqlalchemy.func.regexp_match(Resource.label, PACKAGE_RX) != None,
        #             sqlalchemy.cast(
        #                 sqlalchemy.func.split_part(Resource.label, '.', 2), sqlalchemy.Integer
        #             ),
        #         ),
        #         else_=None,
        #     ),
        #     sqlalchemy.case(
        #         (
        #             sqlalchemy.func.regexp_match(Resource.label, PACKAGE_RX) != None,
        #             sqlalchemy.cast(
        #                 sqlalchemy.func.split_part(Resource.label, '.', 3), sqlalchemy.Integer
        #             ),
        #         ),
        #         else_=None,
        #     ),
        # ]

        # Insert all root resources.
        stmt = (
            sqlalchemy.insert(RootResource)
            .from_select(
                ['root_id', 'label', 'type'],
                sqlalchemy.select(
                    Resource.id,
                    Resource.label,
                    Resource.type,
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
        return result.scalar_one_or_none() or 0
