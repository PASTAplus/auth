import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

from db.models.key import Key

log = daiquiri.getLogger(__name__)

import secrets

# noinspection PyTypeChecker,PyUnresolvedReferences
class KeyInterface:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    async def create_key(self, token_profile_row, description_str, from_dt, to_dt):
        """Create a new key for the given token profile.
        - The key ID is generated using a secure random URL-safe string, and contains 160 bits of
        entropy, like EDI-IDs.
        """
        self.session.add(
            Key(
                profile_id=token_profile_row.id,
                key_id=secrets.token_urlsafe(20),
                description=description_str,
                valid_from=from_dt,
                valid_to=to_dt,
            )
        )

    async def get_key(self, token_profile_row, key_id):
        result = await self.session.execute(
            sqlalchemy.select(Key).where(
                Key.profile_id == token_profile_row.id,
                Key.key_id == key_id,
            )
        )
        return result.scalars().first()

    async def get_keys(self, token_profile_row):
        result = await self.session.execute(
            sqlalchemy.select(Key)
            .where(Key.profile_id == token_profile_row.id)
            .order_by(Key.updated.desc())
        )
        return result.scalars().all()

    async def update_key(self, token_profile_row, key_id, description_str, from_dt, to_dt):
        key_row = await self.get_key(token_profile_row, key_id)
        key_row.description = description_str
        key_row.valid_from = from_dt
        key_row.valid_to = to_dt
        self.session.add(key_row)

    async def delete_key(self, token_profile_row, key_id):
        key_row = await self.get_key(token_profile_row, key_id)
        await self.session.delete(key_row)

    async def is_valid_key(self, token_profile_row, key_id):
        stmt = sqlalchemy.select(
            sqlalchemy.exists().where(
                Key.profile_id == token_profile_row.id,
                Key.key_id == key_id,
                Key.valid_from <= sqlalchemy.func.now(),
                sqlalchemy.func.now() <= Key.valid_to,
            )
        )
        result = await self.session.execute(stmt)
        return bool(result.scalar())

    async def get_profile_by_key_id(self, key_id):
        """Get the profile associated with a valid key ID.
        - If the key ID is not found or not valid (expired or not yet active), return None.
        """
        result = await self.session.execute(
            sqlalchemy.select(Key)
            .options(
                sqlalchemy.orm.selectinload(Key.profile),
            )
            .where(
                Key.key_id == key_id,
                Key.valid_from <= sqlalchemy.func.now(),
                sqlalchemy.func.now() <= Key.valid_to,
            )
        )
        key_row = result.scalars().first()
        return key_row.profile if key_row else None
