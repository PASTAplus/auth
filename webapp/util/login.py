import util.url
import sqlalchemy.exc
import starlette.datastructures

import db.models.profile
import util.avatar
import util.edi_token
import util.old_token
import util.url
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
    fetch_avatar_func,
    avatar_ver,
):
    """After user has successfully authenticated with an IdP, handle the final steps of the login
    process.
    """
    if login_type == 'client':
        return await handle_client_login(
            dbi, target_url, idp_name, idp_uid, common_name, email, fetch_avatar_func, avatar_ver
        )
    elif login_type == 'link':
        return await handle_link_identity(
            dbi,
            token_profile_row,
            idp_name,
            idp_uid,
            common_name,
            email,
            fetch_avatar_func,
            avatar_ver,
        )
    else:
        raise ValueError(f'Unknown login_type: {login_type}')


async def handle_client_login(
    dbi, target_url, idp_name, idp_uid, common_name, email, fetch_avatar_func, avatar_ver
):
    """We are currently signed out and are signing in to a new or existing profile."""
    profile_row, info_msg = await dbi.create_or_update_profile(
        idp_name, idp_uid, common_name, email, fetch_avatar_func, avatar_ver
    )
    await dbi.flush()
    # If this is a linked profile, redirect to the primary profile.
    try:
        profile_row = await dbi.get_primary_profile(profile_row)
        info_msg = """You signed in to a linked profile and have been redirected to your primary
            profile.
        """

    except sqlalchemy.exc.NoResultFound:
        pass

    old_uid = email if idp_name == db.models.profile.IdpName.GOOGLE else idp_uid
    old_token_ = util.old_token.make_old_token(
        uid=old_uid,
        groups=(
            Config.VETTED if idp_name == db.models.profile.IdpName.LDAP else Config.AUTHENTICATED
        ),
    )
    edi_token = await util.edi_token.create(dbi, profile_row)
    return util.url.target(
        target_url,
        token=old_token_,
        edi_token=edi_token,
        edi_id=profile_row.edi_id,
        common_name=profile_row.common_name,
        email=profile_row.email,
        idp_common_name=profile_row.idp_common_name,
        idp_uid=profile_row.idp_uid,
        idp_name=profile_row.idp_name,
        sub=profile_row.idp_uid,
        info_msg=util.url.msg(f'Welcome to the EDI Identity and Access Manager! {info_msg}'),
    )


async def handle_link_identity(
    dbi,
    token_profile_row,
    idp_name,
    idp_uid,
    common_name,
    email,
    fetch_avatar_func,
    avatar_ver,
):
    """We are currently signed in and are linking a new or existing identity to the profile to
    which we are signed in.

    This process is reversible by unlinking the profile.

    Signing in to a linked profile will redirect to the primary profile, so it is only possible to
    be signed in to a primary profile. So, if token_profile_row is in the profile link table, it can
    only be in the primary column.
    """

    # Unknown profile: If we found no profile for the identity, this is the easy case. It's the same
    # as logging in to a new account, except that we also link the new profile, and we don't change
    # the signed in profile.
    try:
        profile_row = await dbi.get_profile_by_idp(idp_name, idp_uid)
    except sqlalchemy.exc.NoResultFound:
        profile_row, _ = await dbi.create_or_update_profile(
            idp_name, idp_uid, common_name, email, fetch_avatar_func, avatar_ver
        )
        await dbi.flush()
        await dbi.create_profile_link(token_profile_row, profile_row.id)
        return util.url.internal(
            '/ui/identity',
            info="""The account you signed in with wasn’t yet linked to a profile. We’ve created a
            new profile for it and linked it to your primary profile. You can now sign in to your
            primary profile using either account. If this wasn’t your intention, you can unlink the
            account, then sign in to it to edit or remove it.
            """,
        )

    # Currently signed in profile: If we found the profile to which we are already signed in, this
    # is a user error.
    if profile_row.id == token_profile_row.id:
        return util.url.internal(
            '/ui/identity',
            error="""The profile you are attempting to link is the profile you're currently signed
            in with (your primary profile).
            """,
        )

    # Linked profile, already linked to this profile: If the profile we found is already linked to
    # the currently signed in profile, this is a user error.
    linked_profile_list = await dbi.get_linked_profile_list(token_profile_row.id)
    if profile_row.id in (row.id for row in linked_profile_list):
        return util.url.internal(
            '/ui/identity',
            error="""The profile you are attempting to link was already linked to the profile you're
            currently signed in to (your primary profile).
            """,
        )

    indirect_linked_profile_id_list = list(
        row.id for row in await dbi.get_linked_profile_list(profile_row.id)
    )

    if not indirect_linked_profile_id_list and not await dbi.is_linked_profile(profile_row.id):
        # Neither a primary nor a linked profile: If the profile we found is not a linked profile,
        # and is not linked to any other profile, we can simply link it to the currently signed in
        # profile.
        await dbi.create_profile_link(token_profile_row, profile_row.id)
        return util.url.internal('/ui/identity', info='Profile linked successfully.')

    # Linked profile, linked to another profile: If the profile we found is a linked profile, we
    # re-link the primary profile to which it is linked, along its linked profiles, to the currently
    # signed in profile. We inform the user that this has happened and that they can undo this by
    # unlinking the account.
    #
    # Primary profile: If the profile we found is a primary profile, it is about to become a linked
    # profile. There is a trigger in the DB that enforces that a profile ID that is in the primary
    # column in the link table, cannot also appear in the linked column. So, if we have found a
    # primary profile, there will be one or more rows in the link table with this profile ID in the
    # primary column, but no rows with this profile ID in the linked column.

    # Delete all links for the other profile, both as primary and as linked.
    await dbi.delete_profile_links(profile_row.id)
    # Create new links from the currently signed in profile to the other profile and to all of
    # its linked profiles.
    await dbi.create_profile_link(token_profile_row, profile_row.id)
    for indirect_linked_profile_id in indirect_linked_profile_id_list:
        await dbi.create_profile_link(token_profile_row, indirect_linked_profile_id)
    return util.url.internal(
        '/ui/identity',
        info="""The profile you linked was already associated with another profile. We’ve now linked
        it and any profiles already linked to it to your primary profile. If this wasn’t your
        intention, you can unlink the profile(s) and sign in to them, then restore the links you
        want to keep.
        """,
    )


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
