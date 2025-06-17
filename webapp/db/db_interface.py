import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio

import db.interface.group
import db.interface.identity
import db.interface.permission
import db.interface.profile
import db.interface.sync
import db.interface.sync
import db.models.group
import db.models.identity
import db.models.permission
import db.models.profile
import util.avatar
import util.profile_cache
import db.interface.util
import util.exc

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class DbInterface(
    db.interface.group.GroupInterface,
    db.interface.identity.IdentityInterface,
    db.interface.permission.PermissionInterface,
    db.interface.profile.ProfileInterface,
    db.interface.sync.SyncInterface,
):
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session
        db.interface.group.GroupInterface.__init__(self, session)
        db.interface.identity.IdentityInterface.__init__(self, session)
        db.interface.permission.PermissionInterface.__init__(self, session)
        db.interface.profile.ProfileInterface.__init__(self, session)
        db.interface.sync.SyncInterface.__init__(self, session)

    @property
    def session(self):
        return self._session

    #
    # Profile and Identity
    #

    async def create_or_update_profile_and_identity(
        self,
        idp_name: db.models.identity.IdpName,
        idp_uid: str,
        common_name: str | None,
        email: str | None,
        has_avatar: bool,
    ) -> db.models.identity.Identity:
        """Create or update a profile and identity.

        See the table definitions for db.models.profile.Profile and Identity for more information on
        the fields.
        """
        # If the identity exists, but the IdPName is UNKNOWN, this is the first login into a
        # skeleton profile and identity which was created via the API. We can now convert these to
        # regular profile and identity by updating both with values from the IdP.
        identity_row = await self.get_identity_by_idp_uid(idp_uid=idp_uid)

        if identity_row is not None and identity_row.idp_name == db.models.identity.IdpName.UNKNOWN:
            assert idp_name != db.models.identity.IdpName.UNKNOWN
            identity_row.idp_name = idp_name
            identity_row.has_avatar = has_avatar
            await self.flush()
            await self.update_profile(
                identity_row.profile, common_name=common_name, email=email, has_avatar=has_avatar
            )
            if has_avatar:
                await util.avatar.copy_identity_to_profile_avatar(identity_row)

        identity_row = await self.get_identity(idp_name=idp_name, idp_uid=idp_uid)

        if identity_row is None:
            profile_row = await self.create_profile(
                edi_id=db.interface.util.get_new_edi_id(),
                common_name=common_name,
                email=email,
                has_avatar=has_avatar,
            )
            identity_row = await self.create_identity(
                profile=profile_row,
                idp_name=idp_name,
                idp_uid=idp_uid,
                common_name=common_name,
                email=email,
                has_avatar=has_avatar,
            )
            # Set the avatar for the profile to the avatar for the identity
            if has_avatar:
                await util.avatar.copy_identity_to_profile_avatar(identity_row)
        else:
            # We do not update the profile if it exists, since the profile belongs to the user, and
            # they may update their profile with their own information. However, we do update
            # the identity, since it is associated with the IdP and may change over time.
            await self.update_identity(
                identity_row, idp_name, idp_uid, common_name, email, has_avatar
            )

        return identity_row

    async def create_skeleton_profile_and_identity(
        self, idp_uid: str
    ) -> db.models.identity.Identity:
        """Create a 'skeleton' EDI profile that can be used in permissions, and which can be logged
        into by the IdP UID.

        This method is idempotent, meaning that if a profile already exists for the provided
        `idp_uid`, it will return the existing profile identifier instead of creating a new one.

        At this point, we don't know (without applying heuristics to the UID) by which IdP the UID
        was issued.

        If and when a user logs into the profile for the first time, the profile and identity are
        updated from 'skeleton' to regular with the information provided by the IdP.
        """
        identity_row = await self.get_identity_by_idp_uid(idp_uid)
        if identity_row is not None:
            return identity_row
        return await self.create_or_update_profile_and_identity(
            idp_name=db.models.identity.IdpName.UNKNOWN,
            idp_uid=idp_uid,
            common_name=None,
            email=None,
            has_avatar=False,
        )

    #
    # Util
    #

    async def flush(self):
        """Flush the current session."""
        # log.debug('#### FLUSH ####')
        return await self._session.flush()

    async def rollback(self):
        """Roll back the current transaction."""
        # log.debug('#### ROLLBACK ####')
        return await self._session.rollback()

    async def commit(self):
        """Commit the current transaction."""
        # log.debug('#### COMMIT ####')
        return await self._session.commit()

    async def execute(self, stmt, params=None):
        """Execute a SQL statement."""
        # log.debug(f'Executing statement: {stmt}')
        return await self._session.execute(stmt, params)
