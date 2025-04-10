import starlette.datastructures

import util.old_token
import util.pasta_jwt
import util.redirect
from config import Config


async def handle_successful_login(
    request,
    udb,
    login_type,
    target_url,
    full_name,
    idp_name,
    idp_uid,
    email,
    has_avatar,
    is_vetted,
):
    """After user has successfully authenticated with an IdP, handle the final steps of the login
    process.
    """
    if login_type == 'client':
        return await handle_client_login(
            udb, target_url, full_name, idp_name, idp_uid, email, has_avatar, is_vetted
        )
    elif login_type == 'link':
        return await handle_link_account(request, udb, idp_name, idp_uid, email, has_avatar)
    else:
        raise ValueError(f'Unknown login_type: {login_type}')


async def handle_client_login(
    udb, target_url, full_name, idp_name, idp_uid, email, has_avatar, is_vetted
):
    """We are currently signed out, and are signing in to a new or existing account."""
    target_url = target_url
    identity_row = await udb.create_or_update_profile_and_identity(
        full_name, idp_name, idp_uid, email, has_avatar
    )
    if idp_name == 'google':
        old_uid = email
    else:
        old_uid = idp_uid
    old_token_ = util.old_token.make_old_token(
        uid=old_uid, groups=Config.VETTED if is_vetted else Config.AUTHENTICATED
    )
    pasta_token = await util.pasta_jwt.make_jwt(udb, identity_row, is_vetted=is_vetted)
    return util.redirect.target(
        target_url,
        token=old_token_,
        pasta_token=pasta_token,
        pasta_id=identity_row.profile.pasta_id,
        full_name=identity_row.profile.full_name,
        email=identity_row.profile.email,
        idp_uid=identity_row.idp_uid,
        idp_name=identity_row.idp_name,
        sub=identity_row.idp_uid,
    )


async def handle_link_account(request, udb, idp_name, idp_uid, email, has_avatar):
    """We are currently signed in, and are linking a new account to the profile to which we are
    signed in.
    """
    # Link new account to the profile associated with the token.
    token_str = request.cookies.get('pasta_token')
    token_obj = util.pasta_jwt.PastaJwt.decode(token_str)
    profile_row = await udb.get_profile(token_obj.pasta_id)
    # Prevent linking an account that is already linked.
    identity_row = await udb.get_identity(idp_name, idp_uid)
    error_msg_str = None
    success_msg_str = None
    if identity_row:
        if identity_row in profile_row.identities:
            error_msg_str = (
                'The account you are attempting to link was already linked to this profile.'
            )
        else:
            error_msg_str = (
                'The account you are attempting to link is already linked to another '
                'profile. If you wish to link the account to this profile instead, '
                'please sign in to the other profile and unlink it there first.'
            )
    else:
        await udb.create_identity(profile_row, idp_name, idp_uid, email, has_avatar)
        success_msg_str = 'Account linked successfully.'
    return util.redirect.internal(
        '/ui/identity', error_msg=error_msg_str, success_msg=success_msg_str
    )


def get_redirect_uri(idp_name):
    url_obj = starlette.datastructures.URL(Config.SERVICE_BASE_URL)
    return url_obj.replace(path=f'{url_obj.path}/callback/{idp_name}')


def pack_state(login_type, target_url):
    """Pack the login type and target URL in to a single string for use as the state parameter in
    the OAuth2 flow."""
    return f'{login_type}:{target_url}'


def unpack_state(state_str: str) -> list[str, str]:
    """Unpack the login type and target URL from a state string.
    :returns: [login_type, target_url]
    """
    # noinspection PyTypeChecker
    return state_str.split(':', maxsplit=1)
