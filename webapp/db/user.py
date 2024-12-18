import datetime
import uuid

import daiquiri
import sqlalchemy.event
import sqlalchemy.orm
import sqlalchemy.pool

import db.base
import db.group
import db.sync

import util

log = daiquiri.getLogger(__name__)


#
# Tables
#


class Profile(db.base.Base):
    __tablename__ = 'profile'
    # At the DB level, we use an 'id' integer primary key for rows, and for foreign key
    # relationships.
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The PASTA ID for the user. This is the primary key for the user in our system. We
    # don't use it as a primary key in the DB, however, since it's a string, and string
    # indexes are less efficient than integer indexes.
    urid = sqlalchemy.Column(sqlalchemy.String, nullable=False, unique=True)
    # The user's given and family names. Initially set to the values provided by the
    # IdP.
    given_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    family_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The email address that the user has chosen as their contact email. Initially set
    # to the email address provided by the IdP.
    email = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # Permit notifications to be sent to this email address.
    email_notifications = sqlalchemy.Column(
        sqlalchemy.Boolean(), nullable=False, default=False
    )
    # Initially false, then set to true when the user accepts the privacy policy.
    privacy_policy_accepted = sqlalchemy.Column(
        sqlalchemy.Boolean(), nullable=False, default=False
    )
    # The date when the user accepted the privacy policy.
    privacy_policy_accepted_date = sqlalchemy.Column(
        sqlalchemy.DateTime(), nullable=True
    )
    organization = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    association = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    has_avatar = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)

    # cascade_backrefs=False:
    # https://sqlalche.me/e/14/s9r1
    # https://sqlalche.me/e/b8d9
    identities = sqlalchemy.orm.relationship(
        'Identity',
        back_populates='profile',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )
    groups = sqlalchemy.orm.relationship(
        'Group',
        back_populates='profile',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )
    group_members = sqlalchemy.orm.relationship(
        'GroupMember',
        back_populates='profile',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )

    @property
    def full_name(self):
        if self.family_name is None:
            return self.given_name
        return f'{self.given_name} {self.family_name}'

    @full_name.setter
    def full_name(self, full_name):
        try:
            self.given_name, self.family_name = full_name.split(' ', 1)
        except ValueError:
            self.given_name, self.family_name = full_name, None

    @property
    def initials(self):
        return ''.join(s[0].upper() for s in self.full_name.split())

    @property
    def avatar_url(self):
        return str(util.get_profile_avatar_url(self))


class Identity(db.base.Base):
    __tablename__ = 'identity'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # Identities have a many-to-one relationship with Profiles. This allows us to find
    # the one Profile that corresponds to a given Identity, and to find all Identities
    # that correspond to a given Profile. The latter is referenced via the backref
    # 'identities' in the Profile. The 'profile_id' declaration creates the physical
    # column in the table which tracks the relationship. Setting 'profile_id' nullable
    # to False forces the identity to be linked to an existing profile. The 'profile'
    # declaration specifies the relationship for use only in the ORM layer.
    profile_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('profile.id'), nullable=False
    )
    # Our name for the IdP. Currently one of 'github', 'google', 'ldap', 'microsoft',
    # 'orcid'.
    # This acts as a namespace for the subject (sub) provided by the IdP.
    idp_name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    # The uid is the unique user ID provided by the IdP. The source of this value varies
    # with the IdP. E.g., for Google, it's the 'sub' (subject) and for ORCID, it's an
    # ORCID on URL form. The value is unique within the IdP's namespace. It is only
    # unique within our system when combined with the idp_name.
    uid = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    # The email address provided by the IdP. This will change if the user updates their
    # email address with the IdP.
    email = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    # The date and time of the first successful authentication with this identity.
    first_auth = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.now
    )
    # The date and time of the most recent successful authentication with this identity.
    last_auth = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )
    # True if an avatar has been successfully downloaded and stored in the file system
    # for this IdP.
    has_avatar = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)

    profile = sqlalchemy.orm.relationship(
        'Profile',
        back_populates='identities',
        cascade_backrefs=False,
    )
    # @property
    # def full_name(self):
    #     if self.family_name is None:
    #         return self.given_name
    #     return f'{self.given_name} {self.family_name}'

    __table_args__ = (
        # Ensure that idp_name and uid are unique together (each IdP has its own
        # namespace for unique identifiers)
        sqlalchemy.UniqueConstraint('idp_name', 'uid', name='idp_name_uid_unique'),
        # Ensure that the idp_name is the name of one of our supported IdPs
        sqlalchemy.CheckConstraint(
            "idp_name IN ('github', 'google', 'ldap', 'microsoft', 'orcid')",
            name='idp_name_check',
        ),
    )


#
# Interface
#


class UserDb:
    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session

    #
    # Profile and Identity
    #
    def create_or_update_profile_and_identity(
        self,
        full_name: str,
        idp_name: str,
        uid: str,
        email: str | None,
        has_avatar: bool,
    ) -> Identity:
        """Create or update a profile and identity.

        See the table definitions for Profile and Identity for more information on the
        fields.
        """
        identity_row = self.get_identity(idp_name=idp_name, uid=uid)
        # Split a full name in to given name and family name. If full_name is a single
        # word, family_name will be None. If full_name is multiple words, the first word
        # will be given_name and the remaining words will be family_name.
        given_name, family_name = (
            full_name.split(' ', 1) if ' ' in full_name else (full_name, None)
        )
        if identity_row is None:
            profile_row = self.create_profile(
                given_name=given_name,
                family_name=family_name,
                email=email,
                has_avatar=has_avatar,
            )
            identity_row = self.create_identity(
                profile=profile_row,
                idp_name=idp_name,
                uid=uid,
                email=email,
                has_avatar=has_avatar,
            )
            # Set the avatar for the profile to the avatar for the identity
            if has_avatar:
                avatar_img = util.get_avatar_path(idp_name, uid).read_bytes()
                util.save_avatar(avatar_img, 'profile', profile_row.urid)

        else:
            assert identity_row.profile is not None
            assert identity_row.idp_name == idp_name
            assert identity_row.uid == uid
            # We do not update the profile if it exists, since the profile belongs to
            # the user, and they may update their profile with their own information.
            #
            # We always update the email address in the identity row, but only update
            # the profile if the profile is new. So if the user has changed their email
            # address with the IdP, the new email address will be stored in the identity
            # row, but the profile will retain the original email address.
            identity_row.email = email
            self.session.commit()
            self.sync_update('identity')

        return identity_row

    def create_profile(
        self,
        given_name: str = None,
        family_name: str = None,
        email: str = None,
        has_avatar: bool = False,
    ):
        new_profile = Profile(
            urid=UserDb.get_new_urid(),
            given_name=given_name,
            family_name=family_name,
            email=email,
            has_avatar=has_avatar,
        )
        self.session.add(new_profile)
        self.session.commit()
        self.sync_update('profile')
        return new_profile

    def get_profile(self, urid):
        query = self.session.query(Profile)
        profile = query.filter(Profile.urid == urid).first()
        return profile

    def get_profiles_by_ids(self, profile_id_list):
        """Get a list of profiles by their IDs.
        The list is returned in the order of the IDs in the input list.
        """
        query = self.session.query(Profile)
        profile_list = query.filter(Profile.id.in_(profile_id_list)).all()
        profile_dict = {p.id: p for p in profile_list}
        return [
            profile_dict[profile_id]
            for profile_id in profile_id_list
            if profile_id in profile_dict
        ]

    def has_profile(self, urid):
        return self.get_profile(urid) is not None

    def update_profile(self, urid, **kwargs):
        profile_row = self.get_profile(urid)
        for key, value in kwargs.items():
            setattr(profile_row, key, value)
        self.session.commit()
        self.sync_update('profile')

    def delete_profile(self, urid):
        profile_row = self.get_profile(urid)
        self.session.delete(profile_row)
        self.session.commit()
        self.sync_update('profile')

    def set_privacy_policy_accepted(self, urid):
        log.debug('Setting privacy policy accepted')
        profile_row = self.get_profile(urid)
        profile_row.privacy_policy_accepted = True
        profile_row.privacy_policy_accepted_date = datetime.datetime.now()
        self.session.commit()

    #
    # Identity
    #

    def create_identity(
        self,
        profile,
        idp_name: str,
        uid: str,
        email: str,
        has_avatar: bool,
    ):
        """Create a new identity for a given profile."""
        new_identity = Identity(
            profile=profile,
            idp_name=idp_name,
            uid=uid,
            email=email,
            has_avatar=has_avatar,
        )
        self.session.add(new_identity)
        self.session.commit()
        self.sync_update('identity')
        return new_identity

    def get_identity(self, idp_name: str, uid: str):
        query = self.session.query(Identity)
        identity = query.filter(
            Identity.idp_name == idp_name, Identity.uid == uid
        ).first()
        return identity

    def get_identity_by_id(self, identity_id):
        query = self.session.query(Identity)
        identity = query.filter(Identity.id == identity_id).first()
        return identity

    def delete_identity(self, profile_row, idp_name: str, uid: str):
        """Delete an identity."""
        identity_row = self.get_identity(idp_name, uid)
        if identity_row not in profile_row.identities:
            raise ValueError(f'Identity {idp_name} {uid} does not belong to profile')
        self.session.delete(identity_row)
        self.session.commit()
        self.sync_update('identity')

    @staticmethod
    def get_new_urid():
        return f'PASTA-{uuid.uuid4().hex}'

    def get_all_profiles(self):
        query = self.session.query(Profile)
        return query.order_by(sqlalchemy.asc(Profile.id)).all()

    def get_all_profiles_generator(self):
        for profile_row in self.session.query(Profile):
            yield profile_row

    #
    # Group
    #

    def create_group(self, profile_row, name, description):
        new_group = db.group.Group(
            grid=UserDb.get_new_urid(),
            profile=profile_row,
            name=name,
            description=description or None,
        )
        self.session.add(new_group)
        self.session.commit()
        self.sync_update('group')
        return new_group

    def get_group(self, profile_row, group_id):
        """Get a group by its ID.
        Raises an exception if the group is not owned by the profile.
        """
        group_row = (
            self.session.query(db.group.Group)
            .filter(
                db.group.Group.id == group_id,
                db.group.Group.profile_id == profile_row.id,
            )
            .first()
        )
        if group_row is None:
            raise ValueError(f'Group {group_id} not found')
        return group_row

    def update_group(self, profile_row, group_id, name, description):
        """Update a group by its ID.
        Raises ValueError if the group is not owned by the profile.
        """
        group_row = self.get_group(profile_row, group_id)
        group_row.name = name
        group_row.description = description or None
        self.session.commit()
        self.sync_update('group')

    def delete_group(self, profile_row, group_id):
        """Delete a group by its ID.
        Raises ValueError if the group is not owned by the profile.
        """
        group_row = self.get_group(profile_row, group_id)
        # Delete group members
        self.session.query(db.group.GroupMember).filter(
            db.group.GroupMember.group_id == group_row.id
        ).delete()
        self.session.delete(group_row)
        self.session.commit()
        self.sync_update('group')

    def add_group_member(self, profile_row, group_id, member_profile_id):
        """Add a member to a group.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the profile
        group_row = self.get_group(profile_row, group_id)
        new_member = db.group.GroupMember(
            group=group_row,
            profile_id=member_profile_id,
        )
        self.session.add(new_member)
        group_row.updated = datetime.datetime.now()
        self.session.commit()
        self.sync_update('group_member')

    def delete_group_member(self, profile_row, group_id, member_profile_id):
        """Delete a member from a group.
        Raises ValueError if the group is not owned by the profile.
        """
        # Check that group is owned by the profile
        group_row = self.get_group(profile_row, group_id)
        member_row = (
            self.session.query(db.group.GroupMember)
            .filter(
                db.group.GroupMember.group_id == group_row.id,
                db.group.GroupMember.profile_id == member_profile_id,
            )
            .first()
        )
        if member_row is None:
            raise ValueError(
                f'Member {member_profile_id} not found in group {group_id}'
            )
        self.session.delete(member_row)
        group_row.updated = datetime.datetime.now()
        self.session.commit()
        self.sync_update('group_member')

    def get_group_member_list(self, profile_row, group_id):
        """Get the members of a group.
        Raises ValueError if the group is not owned by the profile.
        """
        group_row = self.get_group(profile_row, group_id)
        query = self.session.query(db.group.GroupMember)
        return query.filter(db.group.GroupMember.group == group_row).all()

    def get_group_membership_list(self, profile_row):
        """Get the groups that this profile is a member of."""
        query = (
            self.session.query(db.group.Group)
            .join(db.group.GroupMember)
            .filter(db.group.GroupMember.profile == profile_row)
        )
        return query.all()

    def get_group_membership_grid_set(self, profile_row):
        return {group.grid for group in self.get_group_membership_list(profile_row)}

    def leave_group_membership(self, profile_row, group_id):
        """Leave a group.
        Raises ValueError if the member who is leaving does match the profile.

        Note: While this method ultimately performs the same action as delete_group_member,
        it performs different checks.
        """
        member_row = (
            self.session.query(db.group.GroupMember)
            .filter(
                db.group.GroupMember.group_id == group_id,
                db.group.GroupMember.profile_id == profile_row.id,
            )
            .first()
        )
        if member_row is None:
            raise ValueError(f'Member {profile_row.id} not found in group {group_id}')
        member_row.group.updated = datetime.datetime.now()
        self.session.delete(member_row)
        self.session.commit()
        self.sync_update('group_member')

    #
    # Sync
    #

    def sync_update(self, name):
        """Update the timestamp on name"""
        sync_row = self.session.query(db.sync.Sync).filter_by(name=name).first()
        if sync_row is None:
            sync_row = db.sync.Sync(name=name)
            self.session.add(sync_row)
        # No-op update to trigger onupdate
        sync_row.name = sync_row.name
        self.session.commit()

    def get_sync_ts(self):
        """Get the latest timestamp"""
        return self.session.query(sqlalchemy.func.max(db.sync.Sync.updated)).scalar()
