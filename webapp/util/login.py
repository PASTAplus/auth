import datetime
import util.avatar
import starlette.datastructures
import sqlalchemy.exc

import db.models.profile
import util.old_token
import util.edi_token
import util.redirect
from config import Config


async def handle_successful_login(
    request,
    dbi,
    token_profile_row,
    login_type,
    target_url,
    idp_name,
    idp_uid,
    common_name,
    email,
    has_avatar,
    is_vetted,
):
    """After user has successfully authenticated with an IdP, handle the final steps of the login
    process.
    """
    if login_type == 'client':
        return await handle_client_login(
            dbi,
            target_url,
            idp_name,
            idp_uid,
            common_name,
            email,
            has_avatar,
            is_vetted,
        )
    elif login_type == 'link':
        return await handle_link_identity(
            dbi, token_profile_row, idp_name, idp_uid, common_name, email, has_avatar
        )
    else:
        raise ValueError(f'Unknown login_type: {login_type}')


async def handle_client_login(
    dbi, target_url, idp_name, idp_uid, common_name, email, has_avatar, is_vetted
):
    """We are currently signed out, and are signing in with a new or existing identity."""
    target_url = target_url
    identity_row = await dbi.create_or_update_profile(
        idp_name, idp_uid, common_name, email, has_avatar
    )
    await dbi.flush()
    if idp_name == db.models.profile.IdpName.GOOGLE:
        old_uid = email
    else:
        old_uid = idp_uid
    old_token_ = util.old_token.make_old_token(
        uid=old_uid, groups=Config.VETTED if is_vetted else Config.AUTHENTICATED
    )
    edi_token = await util.edi_token.create(dbi, identity_row)
    return util.redirect.target(
        target_url,
        token=old_token_,
        edi_token=edi_token,
        edi_id=identity_row.profile.edi_id,
        common_name=identity_row.common_name,
        email=identity_row.profile.email,
        idp_uid=identity_row.idp_uid,
        idp_name=identity_row.idp_name,
        sub=identity_row.idp_uid,
    )


async def handle_link_identity(
    dbi, token_profile_row, idp_name, idp_uid, common_name, email, has_avatar
):
    """We are currently signed in, and are linking a new or existing identity to the profile to
    which we are signed in.

    In this process, we never move an identity from one profile to another. This makes the process
    reversible.

    Primary profile: If the profile we found is a primary profile, it is about to become a linked
    profile. There is a trigger in the DB that enforces that a profile ID that is on the left side
    in the link table (meaning it's a primary profile), cannot also appear on the right side of the
    table (meaning it's a linked profile). So, if we have found a primary profile, there will be one
    or more rows in the link table with this profile ID on the left side, but no rows with this
    profile ID on the right side.

    Linked profile: If the profile we found is a linked profile, it is about to become linked to
    another primary profile. There is a uniqueness constraint in the DB that enforces that a linked
    profile can be linked to only one primary profile.

    Signing in with an account that is linked to a profile that is itself linked to primary
    profile will redirect to the primary profile, so it is only possible to be signed in to a
    primary profile. In other words, if token_profile_row is in the profile link table, it can only
    be on the primary side (left side).

    The identity we are linking can be one of:

    - Previously unknown: We link it to the currently signed in profile by adding a row in the
    identity link table.

    - Linked to the currently signed in profile: No-op, and inform the user.

    - Linked to a profile that is already linked to the currently signed in profile: No-op, and
    inform the user.

    - Linked to a profile that is not linked to the currently signed in profile: We
    insert a new row in the profile link table.

    - Linked to a profile that is itself linked to other profiles: We update all rows
    in the profile link table that have the other profile as primary to have the currently
    signed in profile as primary instead.

    Examples:

    Identity link table (id-link):
    IdP UID | Profile ID
    uid-1   | prof-1
    uid-2   | prof-1
    uid-3   | prof-2
    uid-4   | prof-3
    uid-5   | prof-20
    uid-6   | prof-20
    uid-7   | prof-30
    uid-8   | prof-31

    Profile link table (prof-link):
    Primary profile ID | linked profile ID
    prof-1 | prof-20
    prof-1 | prof-21
    prof-2 | prof-30
    prof-2 | prof-31

    In the following, the user is signed in to prof-1, and is linking an identity:

    - If the user links a previously unknown identity (uid-100), we link it to prof-1 by inserting a
    new row in id-link, "insert id-link (uid=uid-100, profile=prof-1)".

    - If the user attempts to link an identity already linked to prof-1 (e.g., uid-1 -> prof-1), the
    requested link already exists, and this is a no-op.

    - If the user attempts to link an identity linked to an already linked profile (e.g., uid-5 ->
    prof-20 -> prof-1), the requested link already exists, this is a no-op.

    - If the user attempts to link an identity linked to a profile that has no links (e.g, uid-4 ->
    prof-3), we insert a new row, "insert prof-link (primary=prof-1, link=prof-3)".

    - If the user links an identity linked to a previously unrelated primary profile (e.g, uid-3 ->
    prof-2), we have the following: We know the unrelated profile is a primary profile because it
    appears on the left side in one or more rows in prof-link. We need to insert a new row where it
    is on the right side. Since the same profile ID cannot appear on both sides (enforced by
    trigger), we first update the rows where it appears on the left side, to link those indirectly
    linked profiles directly to prof-1, "update prof-link set primary=prof-1 where link=prof-2",
    then we can insert the new row, "insert prof-link (primary=prof-1, link=prof-2)".

    - If the user links an identity linked to a previously unrelated linked profile (uid-8 ->
    prof-31 -> prof-2), we handle it the same way as the previous case. It's just one more step
    of indirection to find the primary profile (prof-2).
    """
    # If this is a new identity (the IdP UID is not already linked to any profile), link it to
    # the currently signed in profile.
    try:
        identity_row = await dbi.get_profile(idp_name, idp_uid)
    except sqlalchemy.exc.NoResultFound:
        await link_identity(
            dbi, token_profile_row, idp_name, idp_uid, common_name, email, has_avatar
        )
        return util.redirect.internal('/ui/identity', success_msg='Account linked successfully.')
    # If we found an existing identity with this IdP UID, the identity may already be linked to the
    # currently signed in profile, in which case this is a no-op, and we just inform the user.
    if identity_row.id in (row.id for row in token_profile_row.identities):
        return util.redirect.internal(
            '/ui/identity',
            error_msg='The account you are attempting to link was already linked to this profile.',
        )
    # We now know that the identity is linked to another profile.
    # If the other profile is one that we have already linked to the currently signed in profile,
    # this is also a no-op, and we just inform the user.
    linked_profile_list = await dbi.get_linked_profiles(token_profile_row.id)
    if identity_row.profile.id in (row.id for row in linked_profile_list):
        return util.redirect.internal(
            '/ui/identity',
            error_msg="""
                The account you are attempting to link was already linked to this profile via
                another profile.
                """,
        )
    # The other profile is not already linked to the currently signed in profile. We now need to
    # determine if the other profile is a primary profile or a linked profile.
    is_primary = dbi.is_primary_profile(identity_row.profile.id)
    # - If it is a primary profile, we need to both insert a new row in the profile link table,
    #   AND we need to update any rows in the profile link table that have this profile.
    # - If it is not a primary profile, it must be a linked profile. In this case, we only need to
    #   update the existing row in the profile link table to link it to the currently signed in.
    # Both of these conditions can be handled the same way, by first updating any rows in the profile
    # link table that have this profile as primary, then inserting a new row in the profile
    # link table.


    result = await dbi.session.execute(
        sqlalchemy.select(dbi.profile_link_table).filter_by(linked_profile_id=identity_row.profile
        .id)
    )

    # We now know that the identity linked to an unrelated profile.
    # Finally, we now know that the identity is linked to another profile, and that the other
    # profile is not already linked to the currently signed in profile. We now link that profile
    # to the currently signed in profile, AND we link its linked profiles to the currently
    # signed in profile as well.
    other_profile_row = identity_row.profile
    other_linked_profile_id_list = (
        row.id for row in await dbi.get_linked_profiles(other_profile_row.id)
    )

    dbi.delete_profile_links(other_profile_row.id)
    await dbi.create_profile_link(token_profile_row, other_profile_row.id)
    for linked_profile_id in other_linked_profile_id_list:
        await dbi.create_profile_link(token_profile_row, linked_profile_id)
    return util.redirect.internal(
        '/ui/identity',
        success_msg="""
            The account you linked is already associated with another profile. As a result, we have
            linked both the account and the other profile. You can undo this by clicking the
            'Unlink' button next to the account. With the profiles linked, you can use either
            account to sign in and access all data and resources from both profiles.
            """,
    )


async def link_identity(dbi, token_profile_row, idp_name, idp_uid, common_name, email, has_avatar):
    try:
        identity_row = await dbi.get_profile(db.models.profile.IdpName.SKELETON, idp_uid)
        identity_row.idp_name = idp_name
        await dbi.update_profile(
            identity_row.profile, common_name=common_name, email=email, has_avatar=has_avatar
        )
        await dbi.flush()

        identity_row.common_name = common_name
        identity_row.email = email
        identity_row.first_auth = identity_row.first_auth or datetime.datetime.now()
        identity_row.last_auth = datetime.datetime.now()
        identity_row.has_avatar = has_avatar

    except sqlalchemy.exc.NoResultFound:
        pass

    await dbi.create_identity(token_profile_row, idp_name, idp_uid, common_name, email, has_avatar)


def get_redirect_uri(idp_name_str):
    url_obj = starlette.datastructures.URL(Config.SERVICE_BASE_URL)
    return url_obj.replace(path=f'{url_obj.path}/callback/{idp_name_str}')


def pack_state(login_type, target_url):
    """Pack the login type and target URL in to a single string for use as the state parameter in
    the OAuth2 flow."""
    return f'{login_type}:{target_url}'


def unpack_state(state_str: str) -> list[str]:
    """Unpack the login type and target URL from a state string."""
    return state_str.split(':', maxsplit=1)
