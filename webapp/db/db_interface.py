import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio

import db.interface.group
import db.interface.key
import db.interface.permission
import db.interface.profile
import db.interface.search
import db.interface.sync
import db.models.group
import db.models.profile

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class DbInterface(
    db.interface.group.GroupInterface,
    db.interface.key.KeyInterface,
    db.interface.permission.PermissionInterface,
    db.interface.profile.ProfileInterface,
    db.interface.search.SearchInterface,
    db.interface.sync.SyncInterface,
):
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session
        db.interface.group.GroupInterface.__init__(self, session)
        db.interface.key.KeyInterface.__init__(self, session)
        db.interface.permission.PermissionInterface.__init__(self, session)
        db.interface.profile.ProfileInterface.__init__(self, session)
        db.interface.search.SearchInterface.__init__(self, session)
        db.interface.sync.SyncInterface.__init__(self, session)

    @property
    def session(self):
        return self._session

    # Session management

    async def flush(self):
        """Flush the current session."""
        # log.debug('#### FLUSH ####')
        return await self.session.flush()

    async def rollback(self):
        """Roll back the current transaction."""
        # log.debug('#### ROLLBACK ####')
        return await self.session.rollback()

    async def commit(self):
        """Commit the current transaction."""
        # log.debug('#### COMMIT ####')
        return await self.session.commit()

    # Util

    async def execute(self, stmt, params=None):
        """Execute a SQL statement."""
        # log.debug(f'#### EXECUTE: {stmt} ####')
        return await self.session.execute(stmt, params)

    async def delete(self, row):
        """Delete a row"""
        # log.debug('#### DELETE ####')
        return await self.session.delete(row)

    # Debug

    async def dump_raw_query(self, query_str, params=None):
        """Execute a raw SQL query and dump the result to log.

        This is intended for quickly inspecting the state of the database as seen from inside the
        current transaction.

        Example: dump_raw_query('select * from principal')
        """
        result = await self.session.execute(sqlalchemy.text(query_str), params)
        header_str = '#' * 30 + 'RAW QUERY' + '#' * 30
        log.info(header_str)
        log.info(f'Query: {query_str}')
        log.info(f'Params: {params}')
        for row in result:
            log.info(row)
        log.info('#' * len(header_str))
