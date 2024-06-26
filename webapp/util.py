import fastapi
import typing
import urllib.parse
import starlette.responses

import daiquiri

log = daiquiri.getLogger(__name__)


def urlenc(url: str) -> str:
    return urllib.parse.quote(url, safe='')


def get_dn_uid(dn: str) -> str:
    dn_parts = dn.split(',')
    uid = dn_parts[0].split('=')[1]
    return uid


def redirect(base_url: str, **kwargs):
    """Create a Flask response that redirects to the base_url with query parameters"""
    log_dict(log.debug, f'Redirecting to: {base_url}', kwargs)
    return starlette.responses.RedirectResponse(
        f'{base_url}{"?" if kwargs else ""}{build_query_string(**kwargs)}'
    )


def build_query_string(**kwargs) -> str:
    """Build a query string from keyword arguments"""
    return urllib.parse.urlencode(kwargs)


def log_dict(logger: typing.Callable, msg: str, d: dict):
    logger(f'{msg}:')
    for k, v in d.items():
        logger(f'  {k}: {v}')
