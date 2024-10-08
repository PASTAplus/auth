import pprint
import typing
import urllib.parse
import starlette.responses
import json
import datetime

import daiquiri

from config import Config

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


def redirect_target(
    target: str,
    pasta_token: str,
    urid: str,
    full_name: str,
    email: str,
    uid: str,
    idp_name: str,
    idp_token: str | None,
):
    """Create a Flask response that redirects to the final target specified by the
    client.

    This is a wrapper around the general redirect function that ensures a uniform
    set of query parameters returned to the client regardless of which IdP is used.
    """
    # TODO: The query parameters other than the token should be removed from the
    # redirect URI when the transition to the new authentication system is complete,
    # since they are effectively unsigned claims.
    return redirect(
        target,
        token=pasta_token,
        urid=urid,
        cname=full_name,
        email=email,
        uid=uid,
        idp=idp_name,
        idp_token=idp_token,
        # For ezEML
        sub=uid,
    )


def build_query_string(**kwargs) -> str:
    """Build a query string from keyword arguments"""
    return urllib.parse.urlencode(kwargs)


def log_dict(logger: typing.Callable, msg: str, d: dict):
    logger(f'{msg}:')
    for k, v in d.items():
        logger(f'  {k}: {v}')


def get_redirect_uri(idp_name, target):
    return f'{Config.CALLBACK_BASE_URL}/{idp_name}/callback/{target}'


async def split_full_name(full_name: str) -> typing.Tuple[str, str]:
    """Split a full name into given name and family name.

    :returns: A tuple of given_name, family_name
    """
    return full_name.split(' ', 1) if ' ' in full_name else (full_name, '')


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)


async def to_pretty_json(obj: list | dict) -> str:
    json_str = json.dumps(obj, indent=2, sort_keys=True, cls=CustomJSONEncoder)
    # print(json_str)
    return json_str


def pp(obj: list | dict):
    print(pprint.pformat(obj, indent=2, sort_dicts=True))
