import datetime

import daiquiri
import sqlalchemy.ext.hybrid
import sqlalchemy.orm
import sqlalchemy.pool

import db.base

log = daiquiri.getLogger(__name__)


#
# Tables
#


class Group(db.base.Base):
    __tablename__ = 'group'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # Our 'Group Random ID' (GRID) for the group. This is the primary key for the group
    # in our system.
    grid = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    # The profile of the user who created and owns the group.
    profile_id = sqlalchemy.Column(
        sqlalchemy.String, sqlalchemy.ForeignKey('profile.id'), nullable=False
    )
    profile = sqlalchemy.orm.relationship('Profile', back_populates='groups')
    # The name of the group as provided by the user. Can be edited.
    name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    # The description of the group as provided by the user. Can be edited.
    description = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The date and time the group was created.
    created = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    # The date and time the group was last updated.
    updated = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
    # The date and time the group was deleted. If this is not null, the group is
    # considered deleted.
    deleted = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)

    members = sqlalchemy.orm.relationship(
        'GroupMember', back_populates='group', cascade_backrefs=False
    )
    # profiles = sqlalchemy.orm.relationship(
    #     'GroupMember', back_populates='profiles', cascade_backrefs=False
    # )

    @sqlalchemy.ext.hybrid.hybrid_property
    def member_count(self):
        return len(self.members)

    @member_count.expression
    def member_count(cls):
        return (
            sqlalchemy.select([sqlalchemy.func.count(GroupMember.id)])
            .where(GroupMember.group_id == cls.id)
            .label("member_count")
        )


class GroupMember(db.base.Base):
    __tablename__ = 'group_member'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The GRID of the group to which the member belongs.
    group_id = sqlalchemy.Column(
        sqlalchemy.String, sqlalchemy.ForeignKey('group.id'), nullable=False
    )
    # The profile of the user who is a member of the group. Does not include the owner
    # of the group.
    profile_id = sqlalchemy.Column(
        sqlalchemy.String, sqlalchemy.ForeignKey('profile.id'), nullable=False
    )
    # The date and time the user was added to the group.
    added = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )

    group = sqlalchemy.orm.relationship('Group', back_populates='members')
    profile = sqlalchemy.orm.relationship('Profile', back_populates='group_members')

    __table_args__ = (
        # Ensure that group_id and profile_id are unique together.
        sqlalchemy.UniqueConstraint(
            'group_id', 'profile_id', name='group_id_profile_id_unique'
        ),
    )


#
# Interface
#


# class GroupDb:
#     def __init__(self, session: sqlalchemy.orm.Session):
#         self.session = session
#
#     def create_group(
#         self, grid: str, profile_id: str, name: str, description: str | None
#     ) -> Group:
#         new_group = Group(
#             grid=grid,
#             profile_id=profile_id,
#             name=name,
#             description=description,
#         )
#         self.session.add(new_group)
#         self.session.commit()
#         return new_group
#
#     def get_group(self, grid: str) -> Group:
#         query = self.session.query(Group)
#         group = query.filter(Group.grid == grid).first()
#         return group
#
#     def get_all_groups(self):
#         query = self.session.query(Group)
#
#         return query.order_by(sqlalchemy.asc(Group.id)).all()
#
#
#     def get_all_groups_for_profile(self, urid: str):
#         query = self.session.query(Group)
#         return query.filter(Group.profile_id == profile_id).all()


    # #
    # # Profile and Identity
    # #
    # def create_or_update_profile_and_identity(
    #     self,
    #     given_name: str,
    #     family_name: str,
    #     idp_name: str,
    #     uid: str,
    #     email: str | None,
    #     has_avatar: bool,
    #     pasta_token: str,
    # ) -> Identity:
    #     """Create or update a profile and identity.
    #
    #     See the table definitions for Profile and Identity for more information on the
    #     fields.
    #     """
    #     identity_row = self.get_identity(idp_name=idp_name, uid=uid)
    #     if identity_row is None:
    #         profile_row = self.create_profile(
    #             given_name=given_name,
    #             family_name=family_name,
    #             email=email,
    #             has_avatar=has_avatar,
    #         )
    #         identity_row = self.create_identity(
    #             profile=profile_row,
    #             idp_name=idp_name,
    #             uid=uid,
    #             email=email,
    #             pasta_token=pasta_token,
    #             has_avatar=has_avatar,
    #         )
    #         # Set the avatar for the profile to the avatar for the identity
    #         if has_avatar:
    #             avatar_img = util.get_avatar_path(idp_name, uid).read_bytes()
    #             util.save_avatar(avatar_img, 'profile', profile_row.urid)
    #
    #     else:
    #         assert identity_row.profile is not None
    #         assert identity_row.idp_name == idp_name
    #         assert identity_row.uid == uid
    #         # We do not update the profile if it exists, since the profile belongs to
    #         # the user, and they may update their profile with their own information.
    #         #
    #         # TODO: Before we provide a way for users to update their profile, we need
    #         # to make sure ezEML, and other clients, have moved to using the URID as the
    #         # primary key for the user.
    #         #
    #         # We always update the email address in the identity row, but only update
    #         # the profile if the profile is new. So if the user has changed their email
    #         # address with the IdP, the new email address will be stored in the identity
    #         # row, but the profile will retain the original email address.
    #         identity_row.email = email
    #         identity_row.pasta_token = pasta_token
    #         self.session.commit()
    #
    #     return identity_row
    #
    # def create_profile(
    #     self,
    #     given_name: str = None,
    #     family_name: str = None,
    #     email: str = None,
    #     has_avatar: bool = False,
    # ):
    #     new_profile = Profile(
    #         urid=UserDb.get_new_urid(),
    #         given_name=given_name,
    #         family_name=family_name,
    #         email=email,
    #         has_avatar=has_avatar,
    #     )
    #     self.session.add(new_profile)
    #     self.session.commit()
    #     return new_profile
    #
    # def get_profile(self, urid):
    #     query = self.session.query(Profile)
    #     profile = query.filter(Profile.urid == urid).first()
    #     return profile
    #
    # def has_profile(self, urid):
    #     return self.get_profile(urid) is not None
    #
    # def update_profile(self, urid, **kwargs):
    #     profile_row = self.get_profile(urid)
    #     for key, value in kwargs.items():
    #         setattr(profile_row, key, value)
    #     self.session.commit()
    #
    # def is_privacy_policy_accepted(self, urid: str) -> bool:
    #     return self.get_profile(urid).privacy_policy_accepted
    #
    # def set_privacy_policy_accepted(self, urid: str):
    #     profile_row = self.get_profile(urid)
    #     profile_row.privacy_policy_accepted = True
    #     profile_row.privacy_policy_accepted_date = datetime.datetime.now()
    #     self.session.commit()
    #
    # #
    # # Identity
    # #
    #
    # def create_identity(
    #     self,
    #     profile,
    #     idp_name: str,
    #     uid: str,
    #     email: str = None,
    #     pasta_token: str = None,
    #     has_avatar: bool = False,
    # ):
    #     """Create a new identity for a given profile."""
    #     new_identity = Identity(
    #         profile=profile,
    #         idp_name=idp_name,
    #         uid=uid,
    #         email=email,
    #         pasta_token=pasta_token,
    #         has_avatar=has_avatar,
    #     )
    #     self.session.add(new_identity)
    #     self.session.commit()
    #     return new_identity
    #
    # def get_identity(self, idp_name: str, uid: str):
    #     query = self.session.query(Identity)
    #     identity = query.filter(
    #         Identity.idp_name == idp_name, Identity.uid == uid
    #     ).first()
    #     return identity
    #
    # def delete_identity(self, idp_name: str, uid: str):
    #     identity_row = self.get_identity(idp_name, uid)
    #     self.session.delete(identity_row)
    #     self.session.commit()
    #
    # def move_identity(self, idp_name: str, uid: str, new_profile: Profile):
    #     identity_row = self.get_identity(idp_name, uid)
    #     identity_row.profile = new_profile
    #     self.session.commit()
    #
    # @staticmethod
    # def get_new_urid():
    #     return f'PASTA-{uuid.uuid4().hex}'
    #
    # def get_all_profiles(self):
    #     query = self.session.query(Profile)
    #     return query.order_by(sqlalchemy.asc(Profile.id)).all()
