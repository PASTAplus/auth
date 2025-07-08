import urllib.parse

import daiquiri
import starlette.datastructures

import db.models.identity
from config import Config

log = daiquiri.getLogger(__name__)


def url(path_str: str, **query_param_dict) -> starlette.datastructures.URL:
    return starlette.datastructures.URL(f'{Config.ROOT_PATH}{path_str}').include_query_params(
        **query_param_dict
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


# def build_query_string(**query_param_dict) -> str:
#     """Build a query string from keyword arguments using starlette.datastructures.URL"""
#     url = starlette.datastructures.URL("/").include_query_params(**query_param_dict)
#     return str(url).lstrip("/")


def get_idp_logo_url(idp_name: db.models.identity.IdpName):
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
            f'Invalid boolean value: {v}. '
            f'Expected one of: true, false, yes, no, 1, 0 (case insensitive).'
        )
