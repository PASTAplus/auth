import re
import subprocess
import time
import urllib.parse

import daiquiri
import starlette.datastructures

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
