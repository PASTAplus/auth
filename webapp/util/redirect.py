import daiquiri
import starlette.datastructures
import starlette.responses
import starlette.status

import util.login
import util.pretty
from config import Config

log = daiquiri.getLogger(__name__)


def internal(
    path_str: str,
    **query_param_dict,
):
    """Create a Response that redirects to the Auth service root path plus a relative URL. Mainly
    for use after handling a POST request.

    query_param_dict values that evaluate to False cause the entire key/value pair not to be
    included in the query params of the Response.

    This uses a 303 See Other status code, which causes the client to always follow the redirect
    using a GET request.
    """
    url_str = f'{Config.ROOT_PATH}{path_str}'
    util.pretty.log_dict(log.debug, f'Redirecting (303) to: {url_str}', query_param_dict)
    return starlette.responses.RedirectResponse(
        starlette.datastructures.URL(url_str).replace_query_params(
            **{k: v for k, v in query_param_dict.items() if v}
        ),
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )


def idp(
    idp_auth_url: str,
    idp_name: str,
    login_type: str,
    target_url: str,
    **query_param_dict,
):
    """Create a Response that redirects to the IdP with which we will be authenticating, and include
    a cookie with the client's final target.
    """
    url_obj = starlette.datastructures.URL(idp_auth_url)
    url_obj = url_obj.replace_query_params(
        redirect_uri=util.login.get_redirect_uri(idp_name),
        state=util.login.pack_state(login_type, target_url),
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


def target(
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


def client_error(
    target_url: str,
    error_msg: str,
):
    """Create a Response that redirects to the final target specified by the client after an error
    occurs during authentication.
    """
    # TODO: The query parameters other than the token should be removed from the
    # redirect URI when the transition to the new authentication system is complete,
    # since they are effectively unsigned claims.
    log.warning(f'Authentication failed: {error_msg}')
    return redirect(
        target_url,
        error=error_msg,
    )


def redirect(url_str: str, **query_param_dict):
    """Create a Response that redirects to the redirect_url with query parameters.

    This uses a 307 Temporary Redirect status code, which prevents the client from caching the
    redirect, and guarantees that the client will not change the request method and body when the
    redirected request is made.
    """
    util.pretty.log_dict(log.debug, f'Redirecting (307) to: {url_str}', query_param_dict)
    url_obj = starlette.datastructures.URL(url_str)
    url_obj = url_obj.replace_query_params(**query_param_dict)
    return starlette.responses.RedirectResponse(url_obj)
