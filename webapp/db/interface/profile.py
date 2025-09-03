import datetime

import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

import util.edi_id
from config import Config
from db.models.permission import SubjectType, Principal
from db.models.profile import Profile

log = daiquiri.getLogger(__name__)


# noinspection PyTypeChecker,PyUnresolvedReferences
class ProfileInterface:
    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession):
        self._session = session

    @property
    def session(self):
        return self._session

    async def create_profile(
        self,
        common_name: str | None = None,
        email: str | None = None,
        has_avatar: bool = False,
        edi_id: str = None,
        idp_uid: str = None,
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
            edi_id=edi_id,
            common_name=common_name,
            email=email,
            has_avatar=has_avatar,
        )
        self._session.add(new_profile_row)
        await self.flush()
        await self._add_principal(new_profile_row.id, SubjectType.PROFILE)
        return new_profile_row

    async def get_profile(self, edi_id):
        result = await self.execute(
            (
                sqlalchemy.select(Profile)
                .options(
                    sqlalchemy.orm.selectinload(Profile.identities),
                    sqlalchemy.orm.selectinload(Profile.principal),
                )
                .where(Profile.edi_id == edi_id)
            )
        )
        return result.scalar_one()

    async def get_all_profiles(self):
        result = await self.execute(sqlalchemy.select(Profile).order_by(sqlalchemy.asc(Profile.id)))
        return result.scalars().all()

    async def get_all_profiles_generator(self):
        """Get a generator of all profiles, sorted by name, email, with id as tiebreaker."""
        result = await self._session.stream(
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
    #         await self._session.query(db.models.profile.Profile)
    #         .filter(db.models.profile.Profile.id.in_(profile_id_list))
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

    async def link_profiles(self, primary_profile_row, secondary_profile_row):
        """Link two profiles."""
        assert primary_profile_row.id != secondary_profile_row.id


        new_link_row = self._session.add(
            sqlalchemy.insert('ProfileLink').values(
                profile_id=primary_profile_row.id,
                linked_profile_id=secondary_profile_row.id,
            )
        )
        await self.flush()
        return new_link_row


