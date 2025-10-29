import re
import subprocess
import time
import urllib.parse

import daiquiri
import starlette.datastructures
import starlette.responses
import starlette.status

import db.models.profile
import util.login
import util.pretty
from config import Config

CACHE_BUSTER_VERSION = None

log = daiquiri.getLogger(__name__)


def url(path_str: str, **query_param_dict) -> starlette.datastructures.URL:
    return starlette.datastructures.URL(f'{Config.ROOT_PATH}{path_str}').include_query_params(
        **query_param_dict
    )


def url_buster(path_str: str, **query_param_dict) -> starlette.datastructures.URL:
    """Return a URL with a v=VERSION cache buster query parameter."""
    return starlette.datastructures.URL(f'{Config.ROOT_PATH}{path_str}').include_query_params(
        **query_param_dict, v=_get_cache_buster_version()
    )


def get_abs_url(rel_url):
    """Return the absolute URL for the given relative URL."""
    return starlette.datastructures.URL(f'{Config.SERVICE_BASE_URL}').replace(path=rel_url)


def urlenc(url_str: str) -> str:
    return urllib.parse.quote(url_str, safe='')


def build_query_string(**query_param_dict) -> str:
    """Build a query string from keyword arguments"""
    # url_obj = starlette.datastructures.URL(Config.ROOT_PATH).join(rel_url)
    # url_obj = url_obj.replace_query_params(**query_param_dict)
    return urllib.parse.urlencode(query_param_dict)


def get_query_param(url_str: str, param_name: str) -> str | None:
    """Get the value of a query parameter from a URL string.
    - If the parameter is not present, return None.
    - If the parameter is present multiple times, return the first value.
    """
    query_str = starlette.datastructures.URL(url_str).query
    try:
        return urllib.parse.parse_qs(query_str)[param_name][0]
    except (KeyError, IndexError):
        return None


def get_idp_logo_url(idp_name):
    """Return the URL to the logo image for the given IdP."""
    return f'/static/idp-logos/{idp_name.name.lower()}.svg'


def is_true(v: str | None) -> bool:
    """Convert a boolean query parameter value to a boolean."""
    if v is None:
        return False
    assert isinstance(v, str)
    if v.lower() in ('true', '1', 'yes'):
        return True
    elif v.lower() in ('false', '0', 'no'):
        return False
    else:
        raise ValueError(
            f'Invalid boolean value: "{v}". '
            f'Expected one of: true, false, yes, no, 1, 0 (case insensitive).'
        )


def msg(s):
    """Clean up a message string for use as a query parameter and display in the UI."""
    return re.sub(r'\s+', ' ', s).strip()


def _get_cache_buster_version() -> str:
    """Get a version string for cache busting.
    - The result is appended to URLs for static assets to force browsers to reload them when the
    version changes. E.g. /static/style.css?v=VERSION
    - The browser won't cache HTML pages, so there's no need to modify links to templates.
    - If we're running in a Git repo, returns the current Git commit hash.
    - If not, returns a Unix timestamp with second resolution that remains constant for the lifetime
    of the process. As different workers are started, they will likely get different timestamps, in
    which case just hitting a different worker will cause the browser to refresh the assets.
    """
    global CACHE_BUSTER_VERSION
    if CACHE_BUSTER_VERSION is not None:
        return CACHE_BUSTER_VERSION
    try:
        result = subprocess.run(
            ('git', 'rev-parse', 'HEAD'), capture_output=True, text=True, check=True
        )
        CACHE_BUSTER_VERSION = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        CACHE_BUSTER_VERSION = str(int(time.time()))
    return CACHE_BUSTER_VERSION

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
    for k in ('info', 'error'):
        if k in query_param_dict:
            query_param_dict[k] = msg(query_param_dict[k])
    return starlette.responses.RedirectResponse(
        starlette.datastructures.URL(url_str).replace_query_params(
            **{k: v for k, v in query_param_dict.items() if v}
        ),
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )


def idp(
    idp_auth_url: str,
    idp_name: db.models.profile.IdpName,
    login_type: str,
    target_url: str,
    **query_param_dict,
):
    """Create a Response that redirects to the IdP with which we will be authenticating."""
    url_obj = starlette.datastructures.URL(idp_auth_url)
    url_obj = url_obj.replace_query_params(
        redirect_uri=util.login.get_redirect_uri(idp_name.name.lower()),
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
    edi_token: str,
    # TODO: All the following query parameters should be removed from the redirect
    # URI when the transition to the new authentication system is complete, since
    # they are effectively unsigned claims.
    edi_id: str,
    common_name: str,
    email: str,
    idp_common_name: str,
    idp_uid: str,
    idp_name: db.models.profile.IdpName,
    sub: str,
    info_msg: str | None = None,
    error_msg: str | None = None,
):
    """Create Response that redirects to the final target URL, providing the old style and new style
    tokens and other information

    This is the final step in the authentication process and creates a uniform set of query
    parameters and cookies returned to all clients for all authentication flows.

    target_url: The URL to which the client originally requested to be redirected.
    """
    msg_dict = {}
    if info_msg:
        msg_dict['info'] = info_msg
    if error_msg:
        msg_dict['error'] = error_msg

    response = redirect(
        target_url,
        # The old token is passed in 'token'
        token=token,
        # The new token is passed in 'edi_token'
        edi_token=edi_token,
        # TODO: All the following query parameters should be removed from the redirect
        # URI when the transition to the new authentication system is complete, since
        # they are effectively unsigned claims.
        edi_id=edi_id,
        full_name=common_name,
        email=email,
        idp_uid=idp_uid,
        idp_name=idp_name.name.lower(),
        # For ezEML
        common_name=idp_common_name,
        sub=sub,
        **msg_dict,
    )
    # auth-token is the location of the old proprietary token
    response.set_cookie('auth-token', token)
    # edi-token is the location of the new JWT token
    response.set_cookie('edi-token', edi_token)
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
    redirect and guarantees that the client will not change the request method and body when the
    redirected request is made.
    """
    util.pretty.log_dict(log.debug, f'Redirecting (307) to: {url_str}', query_param_dict)
    url_obj = starlette.datastructures.URL(url_str)
    url_obj = url_obj.replace_query_params(**query_param_dict)
    return starlette.responses.RedirectResponse(url_obj)
