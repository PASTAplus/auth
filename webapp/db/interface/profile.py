import datetime

import daiquiri
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

import db.interface.util
import db.models.group
import db.models.identity
import db.models.permission
import db.models.profile
from config import Config

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
        edi_id: str,
        common_name: str = None,
        email: str = None,
        has_avatar: bool = False,
    ):
        new_profile_row = db.models.profile.Profile(
            edi_id=edi_id,
            common_name=common_name,
            email=email,
            has_avatar=has_avatar,
        )
        self._session.add(new_profile_row)
        await self.flush()
        await self._add_principal(new_profile_row.id, db.models.permission.SubjectType.PROFILE)
        return new_profile_row

    async def get_profile(self, edi_id):
        result = await self.execute(
            (
                sqlalchemy.select(db.models.profile.Profile)
                .options(
                    sqlalchemy.orm.selectinload(db.models.profile.Profile.identities),
                    sqlalchemy.orm.selectinload(db.models.profile.Profile.principal),
                )
                .where(db.models.profile.Profile.edi_id == edi_id)
            )
        )
        return result.scalars().first()

    async def get_all_profiles(self):
        result = await self.execute(
            sqlalchemy.select(db.models.profile.Profile).order_by(
                sqlalchemy.asc(db.models.profile.Profile.id)
            )
        )
        return result.scalars().all()

    async def get_all_profiles_generator(self):
        """Get a generator of all profiles, sorted by name, email, with id as tiebreaker."""
        result = await self._session.stream(
            (
                sqlalchemy.select(db.models.profile.Profile, db.models.permission.Principal)
                .join(
                    db.models.permission.Principal,
                    sqlalchemy.and_(
                        db.models.permission.Principal.subject_id == db.models.profile.Profile.id,
                        db.models.permission.Principal.subject_type
                        == db.models.permission.SubjectType.PROFILE,
                    ),
                )
                .order_by(
                    db.models.profile.Profile.common_name,
                    db.models.profile.Profile.email,
                    db.models.profile.Profile.id,
                )
            )
        )
        async for profile_row, principal_row in result:
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
        # Delete all identities associated with the profile.
        await self.execute(
            sqlalchemy.delete(db.models.identity.Identity).where(
                db.models.identity.Identity.profile_id == token_profile_row.id
            )
        )
        # Delete all group memberships associated with the profile.
        await self.execute(
            sqlalchemy.delete(db.models.group.GroupMember).where(
                db.models.group.GroupMember.profile_id == token_profile_row.id
            )
        )
        # TODO: Delete any orphaned groups.
        # await self.execute(
        #     sqlalchemy.delete(db.models.group.Group).where(db.models.group.Group.profile_id == token_profile_row.id)
        # )
        # Delete rules for the profile.
        await self.execute(
            sqlalchemy.delete(db.models.permission.Rule)
            .execution_options(synchronize_session="fetch")
            .where(
                db.models.permission.Rule.id.in_(
                    (
                        await self.execute(
                            sqlalchemy.select(db.models.permission.Rule.id)
                            .join(
                                db.models.permission.Principal,
                                db.models.permission.Principal.id
                                == db.models.permission.Rule.principal_id,
                            )
                            .where(
                                db.models.permission.Principal.subject_id == token_profile_row.id,
                                db.models.permission.Principal.subject_type
                                == db.models.permission.SubjectType.PROFILE,
                            )
                        )
                    ).scalars()
                )
            )
        )
        # TODO: Delete any orphaned resources.
        # Delete the profile itself.
        await self._session.delete(token_profile_row)

    async def set_privacy_policy_accepted(self, token_profile_row):
        token_profile_row.privacy_policy_accepted = True
        token_profile_row.privacy_policy_accepted_date = datetime.datetime.now()

    # System profiles

    # async def create_authenticated_profile(self):
    #     try:
    #         await self.create_profile(
    #             has_avatar=True,
    #         )
    #     except sqlalchemy.exc.IntegrityError:
    #         # Multiple processes may try to create the authenticated profile at the same time, so we
    #         # handle that here.
    #         await self.rollback()
    #     else:
    #         util.avatar.init_authenticated_avatar()

    async def get_public_profile(self):
        """Get the profile for the public user."""
        return await self.get_profile(Config.PUBLIC_EDI_ID)

    async def get_authenticated_profile(self):
        """Get the profile for the authenticated user."""
        return await self.get_profile(Config.AUTHENTICATED_EDI_ID)

    #
    # db.models.profile.Profile History
    #

    async def add_profile_history(
        self,
        token_profile_row,
    ):
        """Add a new profile history entry for the given profile."""
        new_profile_history_row = db.models.profile.ProfileHistory(
            profile_id=token_profile_row.id,
            edi_id=token_profile_row.edi_id,
            created_date=datetime.datetime.now(),
        )
        self._session.add(new_profile_history_row)
        await self.flush()
        return new_profile_history_row

    async def get_profile_history(self, token_profile_row):
        result = await self.execute(
            sqlalchemy.select(db.models.profile.ProfileHistory).where(
                db.models.profile.ProfileHistory.id == token_profile_row.id
            )
        )
        return result.scalars().all()

    async def _merge_profiles(self, token_profile_row, from_profile_row):
        """Merge from_profile into token_profile, then delete from_profile."""

        # Move all permissions granted to from_profile to the token_profile. Since corresponding
        # permissions may already exist for token_profile, we need to check if the permission
        # already exists and update it instead of creating a new one. We also need to keep only the
        # highest permission level.
        async for rule_row in await self._session.stream(
            (
                sqlalchemy.select(
                    db.models.permission.Rule,
                )
                .join(
                    db.models.permission.Resource,
                    db.models.permission.Resource.id == db.models.permission.Rule.resource_id,
                )
                .join(
                    db.models.permission.Principal,
                    db.models.permission.Principal.id == db.models.permission.Rule.principal_id,
                )
                .where(
                    db.models.permission.Principal.subject_id == from_profile_row.id,
                    db.models.permission.Principal.subject_type
                    == db.models.permission.SubjectType.PROFILE,
                )
            )
        ):
            await self._merge_profiles_set_permission(
                rule_row.resource, token_profile_row.principal, rule_row.permission
            )

        await self._delete_profile(from_profile_row)

    async def _delete_profile(self, profile_row):
        # Delete all rules for from_profile
        await self.execute(
            sqlalchemy.delete(db.models.permission.Rule).where(
                db.models.permission.Rule.principal_id == profile_row.principal.id
            )
        )
        # Delete all identities for from_profile
        await self.execute(
            sqlalchemy.delete(db.models.identity.Identity).where(
                db.models.identity.Identity.profile_id == profile_row.id
            )
        )
        # Delete all groups for from_profile
        await self.execute(
            sqlalchemy.delete(db.models.group.Group).where(
                db.models.group.Group.profile_id == profile_row.id
            )
        )
        # Delete all group memberships for from_profile
        await self.execute(
            sqlalchemy.delete(db.models.group.GroupMember).where(
                db.models.group.GroupMember.profile_id == profile_row.id
            )
        )
        # Delete the principal for from_profile
        await self._session.delete(profile_row.principal)
        # Delete the from_profile
        await self._session.delete(profile_row)

    async def _merge_profiles_set_permission(
        self,
        resource_row,
        principal_row,
        permission_level,
    ):
        """Ensure that principal_row has at least the given permission level on the resource.

        This is a no-op if the principal_row already has the given permission level or greater on
        the resource. This means that it is always a no-op if the permission level is 0 (NONE).

        If principal_row has no permission on the resource, a new rule is added with the given
        permission_level.
        """

        if permission_level == 0:
            return

        rule_row = await self._get_rule(resource_row, principal_row)

        if rule_row is None:
            rule_row = db.models.permission.Rule(
                resource=resource_row,
                principal=principal_row,
                permission=permission_level,
            )
            self._session.add(rule_row)
        else:
            rule_row.permission = max(rule_row.permission, permission_level)
