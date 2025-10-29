import hashlib
import secrets

import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

from db.models.key import Key

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class KeyInterface:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    async def _increment_key_use_count(self, secret_str):
        """Atomically increment use_count and set last_used."""
        await self.session.execute(
            sqlalchemy.update(Key)
            .where(Key.secret_hash == self._hash_secret(secret_str))
            .values(use_count=Key.use_count + 1, last_used=sqlalchemy.func.now())
        )

    async def _get_new_secret(self) -> str:
        """The key secret is generated using a secure random URL-safe string, and contains 160 bits
        of entropy, like EDI-IDs. A few bytes of these are used for the preview.
        """
        return secrets.token_urlsafe(20)

    def _hash_secret(self, secret_str: str) -> bytes:
        """Hash the secret using SHA-256.
        - SHA-256 creates a 256-bit / 32-byte hash.
        """
        return hashlib.sha256(secret_str.encode('utf-8')).digest()

    async def create_key(self, token_profile_row, group_id, name_str, valid_from_dt, valid_to_dt):
        """Create a new key for the given token profile.
        - Returns the secret string for the new key.
        """
        secret_str = await self._get_new_secret()
        self.session.add(
            Key(
                profile_id=token_profile_row.id,
                group_id=group_id,
                secret_hash=self._hash_secret(secret_str),
                secret_preview=secret_str[:5],
                name=name_str,
                valid_from=valid_from_dt,
                valid_to=valid_to_dt,
            )
        )
        return secret_str

    async def get_valid_key(self, secret_str):
        """Get a valid key by its secret.
        - Raises sqlalchemy.exc.NoResultFound if the key is not found or not valid (expired or not
        yet active).
        """

        result = await self.session.execute(
            sqlalchemy.select(Key)
            .options(
                sqlalchemy.orm.selectinload(Key.profile),
                sqlalchemy.orm.selectinload(Key.group),
            )
            .where(
                Key.secret_hash == self._hash_secret(secret_str),
                Key.valid_from <= sqlalchemy.func.now(),
                sqlalchemy.func.now() <= Key.valid_to,
            )
        )
        return result.scalar_one()

    async def get_profile_by_valid_uid(self, secret_str):
        """Get the profile associated with a valid key UID.
        - If the key UID is not found or not valid (expired or not yet active), return None.
        - If found and valid, increment the use count and update the last use date for the key.
        """
        try:
            key_row = dbi.get_valid_key(secret_str)
        except sqlalchemy.exc.NoResultFound:
            return None
        await self._increment_key_use_count(secret_str)
        return key_row.profile

    async def get_key(self, secret_str):
        """Get a key by its secret.
        - Raises sqlalchemy.exc.NoResultFound if the key is not found.
        """
        result = await self.session.execute(
            sqlalchemy.select(Key).where(
                Key.secret_hash == self._hash_secret(secret_str),
            )
        )
        return result.scalar_one()

    async def get_owned_key(self, token_profile_row, secret_str):
        """Get a key owned by the given token profile.
        - If the key is not found,or is not owned by the token profile, raise
        sqlalchemy.exc.NoResultFound.
        """
        result = await self.session.execute(
            sqlalchemy.select(Key).where(
                Key.profile_id == token_profile_row.id,
                Key.secret_hash == self._hash_secret(secret_str),
            )
        )
        return result.scalar_one()

    async def get_keys(self, token_profile_row):
        result = await self.session.execute(
            sqlalchemy.select(Key)
            .where(Key.profile_id == token_profile_row.id)
            .order_by(Key.updated.desc())
        )
        return result.scalars().all()

    async def update_key(
        self, token_profile_row, secret_str, group_id, name_str, valid_from_dt, valid_to_dt
    ):
        key_row = await self.get_owned_key(token_profile_row, secret_str)
        key_row.group_id = group_id
        key_row.name = name_str
        key_row.valid_from = valid_from_dt
        key_row.valid_to = valid_to_dt
        self.session.add(key_row)

    async def delete_key(self, token_profile_row, secret_str):
        key_row = await self.get_owned_key(token_profile_row, secret_str)
        await self.session.delete(key_row)
