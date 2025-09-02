import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio

import db.interface.group
import db.interface.identity
import db.interface.permission
import db.interface.profile
import db.interface.search
import db.interface.sync
import db.models.identity
import db.models.profile
import db.models.group
import util.avatar
import util.exc

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class DbInterface(
    db.interface.group.GroupInterface,
    db.interface.identity.IdentityInterface,
    db.interface.permission.PermissionInterface,
    db.interface.profile.ProfileInterface,
    db.interface.search.SearchInterface,
    db.interface.sync.SyncInterface,
):
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session
        db.interface.group.GroupInterface.__init__(self, session)
        db.interface.identity.IdentityInterface.__init__(self, session)
        db.interface.permission.PermissionInterface.__init__(self, session)
        db.interface.profile.ProfileInterface.__init__(self, session)
        db.interface.search.SearchInterface.__init__(self, session)
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
        - A full profile is a profile that has been logged into at least once, and so has a known
        identity provider, and is filled in with user information from the identity provider.
        - A skeleton profile is a profile that has been created via the API, and which does not have
        a known identity provider, and no user information.
        """
        assert idp_name != db.models.identity.IdpName.SKELETON
        try:
            identity_row = await self.get_identity(idp_name, idp_uid)
            # We have a full profile.
        except sqlalchemy.exc.NoResultFound:
            identity_row = None

        # If a full profile and identity does not exist for this login. Check for a skeleton
        # profile.
        if identity_row is None:
            try:
                identity_row = await self.get_identity(db.models.identity.IdpName.SKELETON, idp_uid)
                # We have a skeleton profile and identity. We will upgrade this to a full profile
                # below.
            except sqlalchemy.exc.NoResultFound:
                pass

        # See README.md: Strategy for dealing with Google emails historically used as identifiers.
        # If an identity does not exist under the IdP UID, and we're logging in through Google, we
        # check if there is a skeleton profile with the IdP email as the IdP UID.
        if identity_row is None:
            if idp_name == db.models.identity.IdpName.GOOGLE and email:
                try:
                    identity_row = await self.get_identity(
                        db.models.identity.IdpName.SKELETON, email
                    )
                    # We have a legacy case where the IdP UID is an email address. Fix up the record
                    # idp_uid now, and upgrade to full profile below.
                    identity_row.idp_uid = idp_uid
                except sqlalchemy.exc.NoResultFound:
                    pass

        # If we still haven't found an identity, this is the first login into a new profile and
        # identity. We can now create both and return.
        if identity_row is None:
            profile_row = await self.create_profile(
                common_name=common_name,
                email=email,
                has_avatar=has_avatar,
                idp_uid=idp_uid,
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
            return identity_row

        # We are logging into an existing profile. If this is a skeleton profile, upgrade it to
        # full:
        if identity_row.idp_name == db.models.identity.IdpName.SKELETON:
            identity_row.idp_name = idp_name
            await self.update_profile(
                identity_row.profile, common_name=common_name, email=email, has_avatar=has_avatar
            )
            await dbi.flush()
            if has_avatar:
                await util.avatar.copy_identity_to_profile_avatar(identity_row)

        # Update the identity information (both for existing full and skeleton profiles).
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

        return identity_row

    async def create_skeleton_profile_and_identity(
        self, idp_uid: str
    ) -> db.models.identity.Identity:
        """Create a 'skeleton' EDI profile that can be used in permissions, and which can be logged
        into by the IdP UID.

        This method is idempotent, meaning that if a profile already exists for the provided
        `idp_uid`, it will return the existing profile identifier instead of creating a new one. The
        existing profile may be a skeleton or a full profile.

        At this point, we don't know (without applying heuristics to the UID) by which IdP the UID
        was issued.

        If and when a user logs into the profile for the first time, the profile and identity are
        updated from 'skeleton' to regular with the information provided by the IdP.
        """
        try:
            return await self.get_identity_by_idp_uid(idp_uid)
        except sqlalchemy.exc.NoResultFound:
            pass
        except sqlalchemy.exc.MultipleResultsFound:
            # On transitioning to EDI-IDs, it's very unlikely, but theoretically possible, that
            # multiple identities exist for the same IdP UID.
            raise util.exc.AuthError('Multiple identities found for the same IdP UID')
        # See README.md: Strategy for dealing with Google emails historically used as identifiers.
        # The idp_uid may be an email address. If someone has signed in via Google, and their email
        # address matches the idp_uid for the skeleton profile we are preparing to create, use that
        # identity.
        try:
            return await self.get_identity_by_google_email(idp_uid)
        except sqlalchemy.exc.NoResultFound:
            pass
        profile_row = await self.create_profile(idp_uid=idp_uid)
        return await self.create_identity(profile_row, db.models.identity.IdpName.SKELETON, idp_uid)

    async def is_existing_edi_id(self, edi_id: str) -> bool:
        """Check if the given EDI-ID exists in the database.
        - The EDI-ID can be for a profile or a group.
        """
        if (
            await self.execute(
                sqlalchemy.select(
                    sqlalchemy.exists().where(
                        db.models.profile.Profile.edi_id == edi_id,
                    )
                )
            )
        ).scalar_one():
            return True
        return (
            await self.execute(
                sqlalchemy.select(
                    sqlalchemy.exists().where(
                        db.models.group.Group.edi_id == edi_id,
                    )
                )
            )
        ).scalar_one()

    # Session management

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

    # Util

    async def execute(self, stmt, params=None):
        """Execute a SQL statement."""
        # log.debug(f'#### EXECUTE: {stmt} ####')
        return await self._session.execute(stmt, params)

    async def delete(self, row):
        """Delete a row"""
        # log.debug('#### DELETE ####')
        return await self._session.delete(row)

    # Debug

    async def dump_raw_query(self, query_str, params=None):
        """Execute a raw SQL query and dump the result to log.

        This is intended for quickly inspecting the state of the database as seen from inside the
        current transaction.

        Example: dump_raw_query('select * from principal')
        """
        result = await self._session.execute(sqlalchemy.text(query_str), params)
        header_str = '#' * 30 + 'RAW QUERY' + '#' * 30
        log.info(header_str)
        log.info(f'Query: {query_str}')
        log.info(f'Params: {params}')
        for row in result:
            log.info(row)
        log.info('#' * len(header_str))
