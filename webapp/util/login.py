import starlette.datastructures
import sqlalchemy.exc

import db.models.identity
import util.old_token
import util.pasta_jwt
import util.redirect
from config import Config


async def handle_successful_login(
    request,
    dbi,
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
        return await handle_link_account(
            request, dbi, idp_name, idp_uid, common_name, email, has_avatar
        )
    else:
        raise ValueError(f'Unknown login_type: {login_type}')


async def handle_client_login(
    dbi, target_url, idp_name, idp_uid, common_name, email, has_avatar, is_vetted
):
    """We are currently signed out, and are signing in to a new or existing account."""
    target_url = target_url
    identity_row = await dbi.create_or_update_profile_and_identity(
        idp_name, idp_uid, common_name, email, has_avatar
    )
    if idp_name == db.models.identity.IdpName.GOOGLE:
        old_uid = email
    else:
        old_uid = idp_uid
    old_token_ = util.old_token.make_old_token(
        uid=old_uid, groups=Config.VETTED if is_vetted else Config.AUTHENTICATED
    )
    edi_token = await util.pasta_jwt.make_jwt(dbi, identity_row)
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


async def handle_link_account(request, dbi, idp_name, idp_uid, common_name, email, has_avatar):
    """We are currently signed in, and are linking a new account to the profile to which we are
    signed in.
    """
    # Link new account to the profile associated with the token.
    token_str = request.cookies.get('edi-token')
    token_obj = await util.pasta_jwt.PastaJwt.decode(dbi, token_str)
    profile_row = await dbi.get_profile(token_obj.edi_id)
    # Prevent linking an account that is already linked.
    try:
        identity_row = await dbi.get_identity(idp_name, idp_uid)
    except sqlalchemy.exc.NoResultFound:
        identity_row = None
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
        await dbi.create_identity(profile_row, idp_name, idp_uid, common_name, email, has_avatar)
        success_msg_str = 'Account linked successfully.'
    return util.redirect.internal(
        '/ui/identity', error_msg=error_msg_str, success_msg=success_msg_str
    )


def get_redirect_uri(idp_name_str):
    url_obj = starlette.datastructures.URL(Config.SERVICE_BASE_URL)
    return url_obj.replace(path=f'{url_obj.path}/callback/{idp_name_str}')


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
