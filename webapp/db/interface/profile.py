import datetime

import daiquiri
import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

import db.models.group
import util.avatar
import util.edi_id
from config import Config
from db.models.permission import SubjectType, Principal
from db.models.profile import Profile, ProfileLink, IdpName

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class ProfileInterface:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    async def create_or_update_profile(
        self,
        idp_name: IdpName,
        idp_uid: str | None,
        common_name: str | None,
        email: str | None,
        fetch_avatar_func=None,
        avatar_ver: str | None = None,
    ) -> Profile:
        """Create or update to a full profile.
        - A full profile is a profile that has been logged into at least once, and so has a known
        identity provider, and is filled in with user information, with defaults provided by the
        identity provider.
        - If a skeleton profile already exists for the given idp_uid, it is upgraded to a full
        profile.
        - Skeleton profiles are created in a separate function.
        """
        assert idp_name != IdpName.SKELETON
        info_msg = ""
        try:
            profile_row = await self.get_profile_by_idp(idp_name, idp_uid)
            # We have a full profile.
        except sqlalchemy.exc.NoResultFound:
            profile_row = None
        # If a full profile and identity does not exist for this login. Check for a skeleton
        # profile.
        if profile_row is None:
            try:
                profile_row = await self.get_profile_by_idp(IdpName.SKELETON, idp_uid)
                # We have a skeleton profile. We will upgrade this to a full profile below
                info_msg = """The profile to which you signed in was initially created automatically
                    as a placeholder. As a result, we have now filled in the profile with the
                    information provided by your identity provider.
                """
            except sqlalchemy.exc.NoResultFound:
                pass
        # See README.md: Strategy for dealing with Google emails historically used as identifiers.
        # If an identity does not exist under the IdP UID, and we're logging in through Google, we
        # check if there is a skeleton profile with the IdP email as the IdP UID.
        if profile_row is None:
            if idp_name == IdpName.GOOGLE and email:
                try:
                    profile_row = await self.get_profile_by_idp(IdpName.SKELETON, email)
                    # We have a legacy case where the IdP UID is an email address. Fix up the record
                    # idp_uid now, and upgrade to full profile below.
                    profile_row.idp_uid = idp_uid
                    info_msg = """The profile to which you signed in was initially created
                        automatically as a placeholder, using a legacy Google account. As a result,
                        we have now filled in the profile with the information provided by your
                        identity provider.
                    """
                except sqlalchemy.exc.NoResultFound:
                    pass
        # If we still haven't found a profile, this is the first login into a new profile. We can
        # now create the profile.
        if profile_row is None:
            profile_row = await self.create_profile(
                idp_name=idp_name,
                idp_uid=idp_uid,
                common_name=common_name,
                email=email,
            )
            info_msg = """This is the first time you have signed in with this account, and we have
                created a new profile for you.
            """

        # We now have a profile, either previously existing or newly created.
        # If this is a previously existing skeleton profile, upgrade it to full.
        if profile_row.idp_name == IdpName.SKELETON:
            await self.update_profile(
                profile_row,
                idp_name=idp_name,
                common_name=common_name,
                email=email,
            )
        # Refresh the avatar
        if (
            avatar_ver is not None
            and profile_row.avatar_ver != avatar_ver
            and fetch_avatar_func is not None
        ):
            avatar_img = fetch_avatar_func()
            if avatar_img:
                util.avatar.save_avatar(avatar_img, 'profile', profile_row.edi_id)
                profile_row.avatar_ver = avatar_ver
            else:
                profile_row.avatar_ver = None
        # Update the profile's last_auth time, and first_auth time if not already set.
        profile_row.first_auth = profile_row.first_auth or datetime.datetime.now()
        profile_row.last_auth = datetime.datetime.now()
        return profile_row, info_msg

    async def create_skeleton_profile(self, idp_uid: str) -> Profile:
        """Create a 'skeleton' EDI profile that can be used in permissions, and which can be logged
        into by the IdP UID.
        - A skeleton profile is a profile that has been created via the API, and which does not have
        a known identity provider, and no user information.
        - This method is idempotent, meaning that if a profile already exists for the provided
        `idp_uid`, it will return the existing profile identifier instead of creating a new one. The
        existing profile may be a skeleton or a full profile.
        - At this point, we don't know (without applying heuristics to the UID) by which IdP the UID
        was issued.
        - If and when a user logs into the profile for the first time, the profile is updated from a
        skeleton to regular profile with the information provided by the IdP.
        """
        try:
            return await self.get_profile_by_idp_uid(idp_uid)
        except sqlalchemy.exc.NoResultFound:
            pass
        except sqlalchemy.exc.MultipleResultsFound:
            # We enforce uniqueness of (idp_name, idp_uid), and in practice, the idp_uid is unique
            # by itself because the IdPs use different formats on their UIDs, so this should never
            # happen.
            assert False, 'Unreachable'
        # See README.md: Strategy for dealing with Google emails historically used as identifiers.
        # The idp_uid may be an email address. If someone has signed in via Google, and their email
        # address matches the idp_uid for the skeleton profile we are preparing to create, use that
        # identity.
        try:
            return await self.get_profile_by_google_email(idp_uid)
        except sqlalchemy.exc.NoResultFound:
            pass
        return await self.create_profile(
            idp_name=IdpName.SKELETON,
            idp_uid=idp_uid,
        )

    async def is_existing_edi_id(self, edi_id: str) -> bool:
        """Check if the given EDI-ID exists in the database.
        - The EDI-ID can be for a profile or a group.
        """
        if (
            await self.execute(
                sqlalchemy.select(
                    sqlalchemy.exists().where(
                        Profile.edi_id == edi_id,
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

    async def get_profile(self, edi_id):
        result = await self.execute(
            (
                sqlalchemy.select(Profile)
                .options(
                    sqlalchemy.orm.selectinload(Profile.principal),
                )
                .where(Profile.edi_id == edi_id)
            )
        )
        return result.scalar_one()

    async def get_profile_by_idp(self, idp_name: IdpName, idp_uid: str):
        result = await self.execute(
            (
                sqlalchemy.select(Profile)
                .options(
                    sqlalchemy.orm.selectinload(Profile.principal),
                )
                .where(
                    Profile.idp_name == idp_name,
                    Profile.idp_uid == idp_uid,
                )
            )
        )
        return result.scalar_one()

    async def get_profile_by_idp_uid(self, idp_uid: str):
        """Get an identity by its IdP UID, while ignoring the IdP name.
        An identity is guaranteed to be unique only for IdP UID + IdP name, but in practice, the
        IdP UID is unique by itself.
        """
        result = await self.execute(
            sqlalchemy.select(Profile)
            .options(
                sqlalchemy.orm.selectinload(Profile.principal),
            )
            .where(Profile.idp_uid == idp_uid)
        )
        return result.scalar_one()

    async def get_profile_by_google_email(self, email: str):
        """Get the most recently used identity for a profile by email.
        - See README.md: Strategy for dealing with Google emails historically used as identifiers.
        - This will only return the identity for a full (not skeleton) profile.
        """
        result = await self.execute(
            sqlalchemy.select(Profile)
            .options(
                sqlalchemy.orm.selectinload(Profile.principal),
            )
            .where(
                Profile.idp_name == IdpName.GOOGLE,
                Profile.email == email,
            )
            .order_by(
                Profile.last_auth.desc(),
                Profile.id,
            )
            .limit(1)
        )
        return result.scalar_one()

    async def get_profile_by_id(self, profile_id):
        result = await self.execute(
            sqlalchemy.select(Profile)
            .options(
                sqlalchemy.orm.selectinload(Profile.principal),
            )
            .where(Profile.id == profile_id)
        )
        return result.scalar_one()

    async def create_profile(
        self,
        idp_name: IdpName,
        idp_uid: str = None,
        edi_id: str = None,
        common_name: str | None = None,
        email: str | None = None,
        avatar_ver: str | None = None,
    ):
        """Create a new profile.
        - If the edi_id is provided, it is used as the profile's EDI-ID.
        - If the edi_id is not provided, and the idp_uid is provided, the idp_uid is used to
        generate the EDI-ID.
        - If neither is provided, a new random EDI-ID is generated (used for creating profiles in
        testing).
        """
        if edi_id:
            pass
        elif idp_uid:
            edi_id = util.edi_id.get_edi_id(idp_uid)
        else:
            edi_id = util.edi_id.get_random_edi_id()

        new_profile_row = Profile(
            idp_name=idp_name,
            idp_uid=idp_uid,
            edi_id=edi_id,
            common_name=common_name,
            email=email,
            avatar_ver=avatar_ver,
        )
        self.session.add(new_profile_row)
        await self.flush()
        await self._add_principal(new_profile_row.id, SubjectType.PROFILE)
        return new_profile_row

    async def get_all_profiles(self):
        result = await self.execute(sqlalchemy.select(Profile).order_by(sqlalchemy.asc(Profile.id)))
        return result.scalars().all()

    async def get_all_profiles_generator(self):
        """Get a generator of all profiles, sorted by name, email, with id as tiebreaker."""
        result = await self.session.stream(
            (
                sqlalchemy.select(
                    Profile,
                    Principal,
                )
                .join(
                    Principal,
                    sqlalchemy.and_(
                        Principal.subject_id == Profile.id,
                        Principal.subject_type == SubjectType.PROFILE,
                    ),
                )
                .order_by(
                    Profile.common_name,
                    Profile.email,
                    Profile.id,
                )
            )
        )
        async for profile_row, principal_row in result.yield_per(Config.DB_YIELD_ROWS):
            yield profile_row, principal_row

    # async def get_profiles_by_ids(self, profile_id_list):
    #     """Get a list of profiles by their IDs.
    #     The list is returned in the order of the IDs in the input list.
    #     """
    #     profile_query = (
    #         await self.session.query(Profile)
    #         .filter(Profile.id.in_(profile_id_list))
    #         .all()
    #     )
    #     profile_dict = {p.id: p for p in profile_query}
    #     return [
    #         profile_dict[profile_id] for profile_id in profile_id_list if profile_id in profile_dict
    #     ]

    async def update_profile(self, token_profile_row, **kwargs):
        for key, value in kwargs.items():
            setattr(token_profile_row, key, value)

    async def delete_profile(self, token_profile_row):
        """Delete a profile and all associated data."""
        # All associated data is deleted via cascading deletes.
        await self.delete(token_profile_row)

    async def set_privacy_policy_accepted(self, token_profile_row):
        token_profile_row.privacy_policy_accepted = True
        token_profile_row.privacy_policy_accepted_date = datetime.datetime.now()

    # System profiles

    async def get_public_profile(self):
        """Get the profile for the public user."""
        profile_row = await self.get_profile(Config.PUBLIC_EDI_ID)
        return profile_row

    async def get_authenticated_profile(self):
        """Get the profile for the authenticated user."""
        profile_row = await self.get_profile(Config.AUTHENTICATED_EDI_ID)
        assert profile_row is not None
        return profile_row

    #
    # Profile links
    #

    async def create_profile_link(self, token_profile_row, link_profile_id):
        """Link two profiles."""
        stmt = sqlalchemy.insert(ProfileLink).values(
            profile_id=token_profile_row.id,
            linked_profile_id=link_profile_id,
        )
        await self.session.execute(stmt)

    async def get_link_history_list(self, token_profile_row):
        """Get profiles linked to the given profile ordered by link_date."""
        result = await self.execute(
            (
                sqlalchemy.select(Profile.edi_id, ProfileLink.link_date)
                .join(ProfileLink, ProfileLink.linked_profile_id == Profile.id)
                .where(ProfileLink.profile_id == token_profile_row.id)
                .order_by(ProfileLink.link_date)
            )
        )
        return result.all()

    async def get_linked_profile_list(self, profile_id):
        """Get profiles linked to the given profile."""
        result = await self.execute(
            (
                sqlalchemy.select(Profile)
                .options(
                    sqlalchemy.orm.selectinload(Profile.principal),
                )
                .join(ProfileLink, ProfileLink.linked_profile_id == Profile.id)
                .where(ProfileLink.profile_id == profile_id)
            )
        )
        return result.scalars().all()

    async def is_linked_profile(self, profile_id):
        """Check if the given profile is a linked profile"""
        result = await self.execute(
            sqlalchemy.select(
                sqlalchemy.exists().where(
                    ProfileLink.linked_profile_id == profile_id,
                )
            )
        )
        return result.scalar_one()

    async def delete_profile_links(self, profile_id):
        """Delete all links for the given profile.
        - This removes links both where the profile is the primary profile and where it is the
        linked profile.
        """
        await self.session.execute(
            sqlalchemy.delete(ProfileLink).where(
                sqlalchemy.or_(
                    ProfileLink.profile_id == profile_id,
                    ProfileLink.linked_profile_id == profile_id,
                )
            )
        )

    async def unlink_profile(self, token_profile_row, link_profile_id):
        """Unlink the given profile from the token profile."""
        await self.session.execute(
            sqlalchemy.delete(ProfileLink).where(
                ProfileLink.profile_id == token_profile_row.id,
                ProfileLink.linked_profile_id == link_profile_id,
            )
        )

    async def get_primary_profile(self, profile_row):
        """Get the primary profile for the given linked profile."""
        result = await self.execute(
            (
                sqlalchemy.select(Profile)
                .options(
                    sqlalchemy.orm.selectinload(Profile.principal),
                )
                .join(ProfileLink, ProfileLink.profile_id == Profile.id)
                .where(ProfileLink.linked_profile_id == profile_row.id)
            )
        )
        return result.scalar_one()

    #
    # Avatar
    #

    async def update_avatar_ver(self, token_profile_row, avatar_ver):
        token_profile_row.avatar_ver = avatar_ver
        await self.flush()

    async def get_avatar_ver(self, token_profile_row):
        return token_profile_row.avatar_ver
