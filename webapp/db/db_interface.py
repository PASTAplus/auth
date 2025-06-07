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

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class DbInterface(
    db.interface.group.GroupDb,
    db.interface.identity.IdentityDb,
    db.interface.permission.PermissionDb,
    db.interface.profile.ProfileDb,
    db.interface.sync.SyncDb,
):
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session
        db.interface.group.GroupDb.__init__(self, session)
        db.interface.identity.IdentityDb.__init__(self, session)
        db.interface.permission.PermissionDb.__init__(self, session)
        db.interface.profile.ProfileDb.__init__(self, session)
        db.interface.sync.SyncDb.__init__(self, session)

    @property
    def session(self):
        return self._session

    #
    # db.models.profile.Profile and Identity
    #

    async def create_or_update_profile_and_identity(
        self,
        idp_name: str,
        idp_uid: str,
        common_name: str,
        email: str | None,
        has_avatar: bool,
    ) -> db.models.identity.Identity:
        """Create or update a profile and identity.

        See the table definitions for db.models.profile.Profile and Identity for more information on the
        fields.
        """
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
                avatar_img = util.avatar.get_avatar_path(idp_name, idp_uid).read_bytes()
                util.avatar.save_avatar(avatar_img, 'profile', profile_row.edi_id)
        else:
            # We do not update the profile if it exists, since the profile belongs to
            # the user, and they may update their profile with their own information.
            await self.update_identity(
                identity_row, idp_name, idp_uid, common_name, email, has_avatar
            )

        # Undo commit()
        # identity_row = await self.get_identity(idp_name=idp_name, idp_uid=idp_uid)

        return identity_row

    #
    # db.models.permission.Principal
    #

    async def get_principal_id_query(self, token_profile_row):
        """Return a query that returns the principal IDs for all principals that the profile has
        access to.

        The returned list includes the principal IDs of:
            - The profile itself (the 'sub' field)
            - All groups in which this profile is a member (included in 'principals' field)
            - the Public Access profile  (included in 'principals' field)
            - the Authenticated Access profile  (included in 'principals' field)
        """
        return (
            sqlalchemy.select(db.models.permission.Principal.id)
            .outerjoin(
                db.models.profile.Profile,
                sqlalchemy.and_(
                    db.models.profile.Profile.id == db.models.permission.Principal.subject_id,
                    db.models.permission.Principal.subject_type
                    == db.models.permission.SubjectType.PROFILE,
                ),
            )
            .outerjoin(
                db.models.group.Group,
                sqlalchemy.and_(
                    db.models.group.Group.id == db.models.permission.Principal.subject_id,
                    db.models.permission.Principal.subject_type
                    == db.models.permission.SubjectType.GROUP,
                ),
            )
            .outerjoin(
                db.models.group.GroupMember,
                sqlalchemy.and_(
                    db.models.group.GroupMember.group_id == db.models.group.Group.id,
                    db.models.group.GroupMember.profile_id == token_profile_row.id,
                ),
            )
            .where(
                sqlalchemy.or_(
                    # db.models.permission.Principal ID of the db.models.profile.Profile
                    sqlalchemy.and_(
                        db.models.permission.Principal.subject_id == token_profile_row.id,
                        db.models.permission.Principal.subject_type
                        == db.models.permission.SubjectType.PROFILE,
                    ),
                    # Public Access
                    sqlalchemy.and_(
                        db.models.permission.Principal.subject_id
                        == await util.profile_cache.get_public_access_profile_id(self),
                        db.models.permission.Principal.subject_type
                        == db.models.permission.SubjectType.PROFILE,
                    ),
                    # Authorized access
                    sqlalchemy.and_(
                        db.models.permission.Principal.subject_id
                        == await util.profile_cache.get_authenticated_access_profile_id(self),
                        db.models.permission.Principal.subject_type
                        == db.models.permission.SubjectType.PROFILE,
                    ),
                    # Groups in which the profile is a member
                    db.models.group.GroupMember.profile_id == token_profile_row.id,
                )
            )
        )

    async def get_equivalent_principal_edi_id_set(self, token_profile_row):
        """Get a set of EDI-IDs for all principals that the profile has access to.

        Note: This includes the EDI-ID for the profile itself, which should not be included in
        the 'principals' field of the JWT.
        """
        # Get the principal IDs for all principals that the profile has access to.
        principal_ids = (
            (await self.execute(await self.get_principal_id_query(token_profile_row)))
            .scalars()
            .all()
        )
        # Convert principal IDs to EDI-IDs.
        stmt = (
            sqlalchemy.select(
                sqlalchemy.case(
                    (
                        db.models.permission.Principal.subject_type
                        == db.models.permission.SubjectType.GROUP,
                        db.models.group.Group.edi_id,
                    ),
                    else_=db.models.profile.Profile.edi_id,
                )
            )
            .select_from(db.models.permission.Principal)
            .outerjoin(
                db.models.group.Group,
                sqlalchemy.and_(
                    db.models.group.Group.id == db.models.permission.Principal.subject_id,
                    db.models.permission.Principal.subject_type
                    == db.models.permission.SubjectType.GROUP,
                ),
            )
            .outerjoin(
                db.models.profile.Profile,
                sqlalchemy.and_(
                    db.models.profile.Profile.id == db.models.permission.Principal.subject_id,
                    db.models.permission.Principal.subject_type
                    == db.models.permission.SubjectType.PROFILE,
                ),
            )
            .where(db.models.permission.Principal.id.in_(principal_ids))
        )

        return set((await self.execute(stmt)).scalars().all())

    async def _add_principal(self, subject_id, subject_type):
        """Insert a principal into the database.

        subject_id and subject_type are unique together.
        """
        new_principal_row = db.models.permission.Principal(
            subject_id=subject_id, subject_type=subject_type
        )
        self._session.add(new_principal_row)
        await self.flush()
        return new_principal_row

    async def get_principal(self, principal_id):
        """Get a principal by its ID."""
        result = await self.execute(
            sqlalchemy.select(db.models.permission.Principal).where(
                db.models.permission.Principal.id == principal_id
            )
        )
        return result.scalars().first()

    async def get_principal_by_subject(self, subject_id, subject_type):
        """Get a principal by its entity ID and type."""
        result = await self.execute(
            sqlalchemy.select(db.models.permission.Principal).where(
                db.models.permission.Principal.subject_id == subject_id,
                db.models.permission.Principal.subject_type == subject_type,
            )
        )
        return result.scalars().first()

    async def get_principal_by_profile(self, profile_row):
        """Get the principal for a profile."""
        result = await self.execute(
            sqlalchemy.select(db.models.permission.Principal).where(
                db.models.permission.Principal.subject_id == profile_row.id,
                db.models.permission.Principal.subject_type
                == db.models.permission.SubjectType.PROFILE,
            )
        )
        return result.scalars().first()

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
