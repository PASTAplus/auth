import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

from db.models.sync import Sync

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class SyncInterface:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    async def sync_update(self, name):
        """Update or create a sync row with the given name."""
        result = await self.execute(
            sqlalchemy.select(Sync).where(Sync.name == name)
        )
        sync_row = result.scalar_one_or_none()
        if sync_row is None:
            sync_row = Sync(name=name)
            self._session.add(sync_row)
        # No-op update to trigger onupdate
        sync_row.name = sync_row.name

    async def get_sync_ts(self):
        """Get the latest timestamp."""
        result = await self.execute(
            sqlalchemy.select(sqlalchemy.func.max(Sync.updated))
        )
        return result.scalar_one_or_none()
