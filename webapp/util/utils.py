import urllib.parse

import daiquiri
import starlette.datastructures
import starlette.responses
import starlette.status
import starlette.templating

import util.old_token
import util.pasta_jwt
import util.pretty
from config import Config

log = daiquiri.getLogger(__name__)


def url(path_str: str, **query_param_dict) -> starlette.datastructures.URL:
    return starlette.datastructures.URL(
        f'{Config.ROOT_PATH}{path_str}'
    ).include_query_params(**query_param_dict)


def urlenc(url: str) -> str:
    return urllib.parse.quote(url, safe='')


# Redirects


def redirect_internal(
    path_str: str,
    **query_param_dict,
):
    """Create a Response that redirects to the Auth service root path plus a relative
    URL. Mainly for use after handling a POST request.

    This uses a 303 See Other status code, which causes the client to always follow
    the redirect using a GET request.
    """
    url_str = f'{Config.ROOT_PATH}{path_str}'
    util.pretty.log_dict(log.debug, f'Redirecting (303) to: {url_str}', query_param_dict)
    return starlette.responses.RedirectResponse(
        starlette.datastructures.URL(url_str).replace_query_params(**query_param_dict),
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )


def redirect_to_idp(
    idp_auth_url: str,
    idp_name: str,
    login_type: str,
    target_url: str,
    **query_param_dict,
):
    """Create a Response that redirects to the IdP with which we will be authenticating,
    and include a cookie with the client's final target.
    """
    url_obj = starlette.datastructures.URL(idp_auth_url)
    url_obj = url_obj.replace_query_params(
        redirect_uri=get_redirect_uri(idp_name),
        state=pack_state(login_type, target_url),
        **query_param_dict,
    )
    log.debug(f'redirect_to_idp(): {url_obj}')
    return starlette.responses.RedirectResponse(
        url_obj,
        # RedirectResponse returns 307 Temporary Redirect by default.
        # 302: Browser does not cache, and follows with GET.
        # 307: Browser does not cache, and follows with same method as original request.
        status_code=starlette.status.HTTP_302_FOUND,
    )


def handle_successful_login(
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
    """After user has successfully authenticated with an IdP, handle the final steps of
    the login process.
    """
    if login_type == 'client':
        return handle_client_login(
            udb, target_url, full_name, idp_name, idp_uid, email, has_avatar, is_vetted
        )
    elif login_type == 'link':
        return handle_link_account(request, udb, idp_name, idp_uid, email, has_avatar)
    else:
        raise ValueError(f'Unknown login_type: {login_type}')


def handle_client_login(
    udb, target_url, full_name, idp_name, idp_uid, email, has_avatar, is_vetted
):
    """We are currently signed out, and are signing in to a new or existing account."""
    target_url = target_url
    identity_row = udb.create_or_update_profile_and_identity(
        full_name, idp_name, idp_uid, email, has_avatar
    )
    if idp_name == 'google':
        old_uid = email
    else:
        old_uid = idp_uid
    old_token_ = util.old_token.make_old_token(
        uid=old_uid, groups=Config.VETTED if is_vetted else Config.AUTHENTICATED
    )
    pasta_token = util.pasta_jwt.make_jwt(udb, identity_row, is_vetted=is_vetted)
    return redirect_final(
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


def handle_link_account(request, udb, idp_name, idp_uid, email, has_avatar):
    """We are currently signed in, and are linking a new account to the profile we are signed
    in to.
    """
    # Link new account to the profile associated with the token.
    token_str = request.cookies.get('pasta_token')
    token_obj = util.pasta_jwt.PastaJwt.decode(token_str)
    profile_row = udb.get_profile(token_obj.pasta_id)
    # Prevent linking an account that is already linked.
    identity_row = udb.get_identity(idp_name, idp_uid)
    if identity_row:
        if identity_row in profile_row.identities:
            msg_str = (
                'The account you are attempting to link was already linked to this '
                'profile.'
            )
        else:
            msg_str = (
                'The account you are attempting to link is already linked to another '
                'profile. If you wish to link the account to this profile instead, '
                'please sign in to the other profile and unlink it there first.'
            )
    else:
        udb.create_identity(profile_row, idp_name, idp_uid, email, has_avatar)
        msg_str = 'Account linked successfully.'
    return redirect_internal('/ui/identity', msg=msg_str)


def redirect_final(
    target_url: str,
    token: str,
    pasta_token: str,
    # TODO: All the following query parameters should be removed from the redirect
    # URI when the transition to the new authentication system is complete, since
    # they are effectively unsigned claims.
    pasta_id: str,
    full_name: str,
    email: str,
    idp_uid: str,
    idp_name: str,
    sub: str,
):
    """Create Response that redirects to the final target URL, providing the old style and new style
    tokens, and other information

    This is the final step in the authentication process, and creates a uniform set of query
    parameters and cookies returned to all clients for all authentication flows.

    target_url: The URL to which the client originally requested to be redirected.
    """
    response = redirect(
        target_url,
        # The old token is passed in 'token'
        token=token,
        # The new token is passed in 'pasta_token'
        pasta_token=pasta_token,
        # TODO: All the following query parameters should be removed from the redirect
        # URI when the transition to the new authentication system is complete, since
        # they are effectively unsigned claims.
        pasta_id=pasta_id,
        cname=full_name,
        email=email,
        idp_uid=idp_uid,
        idp_name=idp_name,
        # For ezEML
        sub=sub,
    )
    # auth-token is the location of the old proprietary token
    response.set_cookie('auth-token', token)
    # pasta_token is the location of the new JWT token
    response.set_cookie('pasta_token', pasta_token)
    return response


def redirect_to_client_error(
    target_url: str,
    error_msg: str,
):
    """Create a Response that redirects to the final target specified by the client
    after an error occurs during authentication.
    """
    # TODO: The query parameters other than the token should be removed from the
    # redirect URI when the transition to the new authentication system is complete,
    # since they are effectively unsigned claims.
    log.warn(f'Authentication failed: {error_msg}')
    return redirect(
        target_url,
        error=error_msg,
    )


def redirect(url_str: str, **query_param_dict):
    """Create a Response that redirects to the redirect_url with query parameters.

    This uses a 307 Temporary Redirect status code, which prevents the client from
    caching the redirect, and guarantees that the client will not change the request
    method and body when the redirected request is made.
    """
    util.pretty.log_dict(log.debug, f'Redirecting (307) to: {url_str}', query_param_dict)
    url_obj = starlette.datastructures.URL(url_str)
    url_obj = url_obj.replace_query_params(**query_param_dict)
    # f'{base_url}{"?" if query_param_dict else ""}{build_query_string(**query_param_dict)}'
    return starlette.responses.RedirectResponse(url_obj)


#


def build_query_string(**query_param_dict) -> str:
    """Build a query string from keyword arguments"""
    # url_obj = starlette.datastructures.URL(Config.ROOT_PATH).join(rel_url)
    # url_obj = url_obj.replace_query_params(**query_param_dict)
    return urllib.parse.urlencode(query_param_dict)


def pack_state(login_type, target_url):
    """Pack the login type and target URL in to a single string for use as the
    state parameter in the OAuth2 flow."""
    return f'{login_type}:{target_url}'


def unpack_state(state_str: str) -> list[str, str]:
    """Unpack the login type and target URL from a state string.
    :returns: [login_type, target_url]
    """
    # noinspection PyTypeChecker
    return state_str.split(':', maxsplit=1)


def get_redirect_uri(idp_name):
    url_obj = starlette.datastructures.URL(Config.SERVICE_BASE_URL)
    return url_obj.replace(path=f'{url_obj.path}/callback/{idp_name}')


def get_idp_logo_url(idp_name: str):
    """Return the URL to the logo image for the given IdP."""
    return f'/static/idp-logos/{idp_name}.svg'
