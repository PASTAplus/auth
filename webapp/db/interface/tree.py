import sqlalchemy
import re

import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio
import db.interface.util
from db.models.tree import (
    RootResource,
)
from db.models.permission import Resource

from db.models.profile import Profile
import db.resource_tree
import util.avatar
import util.profile_cache
from config import Config

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class TreeInterface:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    async def update_tree(self):
        """Copy all root nodes from the Resource table to the RootResource table."""
        # Delete all existing root resources.
        await self._session.execute(sqlalchemy.delete(RootResource))
        await self._session.execute(sqlalchemy.text('alter sequence root_id_seq restart with 1'))

        # Order resources by label, with a special case for scope.id.version package identifiers.
        # Labels not matching the pattern are ordered by the full string value.
        package_rx = '^[^.,]+\.[0-9]+\.[0-9]+$'
        order_by_clause = [
            sqlalchemy.case(
                (
                    sqlalchemy.func.regexp_match(Resource.label, package_rx) != None,
                    sqlalchemy.func.split_part(Resource.label, '.', 1),
                ),
                else_=Resource.label,
            ),
            sqlalchemy.case(
                (
                    sqlalchemy.func.regexp_match(Resource.label, package_rx) != None,
                    sqlalchemy.cast(
                        sqlalchemy.func.split_part(Resource.label, '.', 2), sqlalchemy.Integer
                    ),
                ),
                else_=None,
            ),
            sqlalchemy.case(
                (
                    sqlalchemy.func.regexp_match(Resource.label, package_rx) != None,
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
            sqlalchemy.select(RootResource)
            .order_by(RootResource.id)
            .offset(start_idx)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


    async def get_root_count(self):
        """Get the count of root resources."""
        stmt = sqlalchemy.select(sqlalchemy.func.count(RootResource.id))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() or 0
