import datetime

import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

from db.models.identity import IdpName, Identity
from db.models.profile import Profile

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class IdentityInterface:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    async def create_identity(
        self,
        profile,
        idp_name: IdpName,
        idp_uid: str,
        common_name: str | None,
        email: str | None,
        has_avatar: bool,
    ):
        """Create a new identity for a given profile."""
        new_identity_row = Identity(
            profile=profile,
            idp_name=idp_name,
            idp_uid=idp_uid,
            common_name=common_name,
            email=email,
            has_avatar=has_avatar,
        )
        self._session.add(new_identity_row)
        await self.flush()
        return new_identity_row

    async def update_identity(
        self, identity_row, idp_name, idp_uid, common_name, email, has_avatar
    ):
        assert identity_row.idp_name in (idp_name, IdpName.UNKNOWN)
        assert identity_row.idp_uid == idp_uid
        # We always update the email address and common name in the identity row, but only set these
        # in the profile when the profile is first created. So if the user has updated their info
        # with the IdP, the updated info will be stored in the identity, but corresponding info in
        # the profile remains unchanged.
        identity_row.common_name = common_name
        identity_row.email = email
        identity_row.first_auth = identity_row.first_auth or datetime.datetime.now()
        identity_row.last_auth = datetime.datetime.now()
        # Normally, has_avatar will be True from the first time the user logs in with the identity.
        # More rarely, it will go from False to True, if a user did not initially have an avatar at
        # the IdP, but then creates one. More rarely still (if at all possible), this may go from
        # True to False, if the user removes their avatar at the IdP. In this latter case, the
        # avatar image in the filesystem will be orphaned here.
        identity_row.has_avatar = has_avatar

    async def get_identity(self, idp_name: IdpName, idp_uid: str):
        result = await self.execute(
            (
                sqlalchemy.select(Identity)
                .options(sqlalchemy.orm.selectinload(Identity.profile))
                .where(
                    Identity.idp_name == idp_name,
                    Identity.idp_uid == idp_uid,
                )
            )
        )
        return result.scalar_one()

    async def get_identity_by_idp_uid(self, idp_uid: str):
        """Get an identity by its IdP UID, while ignoring the IdP name.
        An identity is guaranteed to be unique only for IdP UID + IdP name, but in practice, the
        IdP UID is unique by itself.
        """
        result = await self.execute(
            sqlalchemy.select(Identity)
            .options(sqlalchemy.orm.selectinload(Identity.profile))
            .where(Identity.idp_uid == idp_uid)
        )
        return result.scalar_one()

    async def get_identity_by_email(self, email: str):
        """Get the most recently used identity for a profile by email."""
        result = await self.execute(
            sqlalchemy.select(Identity)
            .options(sqlalchemy.orm.selectinload(Identity.profile))
            .where(Identity.email == email)
            .order_by(
                Identity.last_auth.desc(),
                Identity.id,
            )
            .limit(1)
        )
        return result.scalar_one()

    async def get_identity_by_id(self, identity_id):
        result = await self.execute(
            sqlalchemy.select(Identity)
            .options(sqlalchemy.orm.selectinload(Identity.profile))
            .where(Identity.id == identity_id)
        )
        return result.scalar_one()

    async def get_identity_by_edi_id(self, edi_id: str):
        """Get the most recently used identity for a profile by its EDI-ID."""
        result = await self.execute(
            sqlalchemy.select(Identity)
            .join(Profile)
            .options(sqlalchemy.orm.selectinload(Identity.profile))
            .where(Profile.edi_id == edi_id)
            .order_by(
                Identity.last_auth.desc(),
                Identity.id,
            )
            .limit(1)
        )
        return result.scalar_one()

    async def delete_identity(self, token_profile_row, idp_name: IdpName, idp_uid: str):
        """Delete an identity from a profile."""
        try:
            identity_row = await self.get_identity(idp_name, idp_uid)
        except sqlalchemy.exc.NoResultFound:
            raise ValueError(f'Identity not found for idp_name="{idp_name}" idp_uid="{idp_uid}"')
        if identity_row not in token_profile_row.identities:
            raise ValueError(
                f'Identity does not belong to profile. idp_name="{idp_name}" idp_uid="{idp_uid}"'
            )
        await self._session.delete(identity_row)
