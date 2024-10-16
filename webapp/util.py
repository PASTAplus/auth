import datetime
import io
import json
import pprint
import typing
import urllib.parse

import PIL
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import daiquiri
import starlette.datastructures
import starlette.responses
import starlette.status
import starlette.templating

import filesystem
from config import Config

AVATAR_FONT = PIL.ImageFont.truetype(
    Config.AVATAR_FONT_PATH,
    Config.AVATAR_HEIGHT * Config.AVATAR_FONT_HEIGHT,
)

log = daiquiri.getLogger(__name__)


def url(path_str: str, **query_param_dict) -> starlette.datastructures.URL:
    return starlette.datastructures.URL(
        f'{Config.ROOT_PATH}{path_str}'
    ).include_query_params(**query_param_dict)


def urlenc(url: str) -> str:
    return urllib.parse.quote(url, safe='')


def get_dn_uid(dn: str) -> str:
    dn_parts = dn.split(',')
    uid = dn_parts[0].split('=')[1]
    return uid


def redirect_to_idp(
    idp_auth_url: str,
    idp_name: str,
    target_url: str,
    **kwargs,
):
    """Create a RedirectResponse with location set to the IdP with which we will be
    authenticating, and include a cookie with the client's final target."""
    url_obj = starlette.datastructures.URL(idp_auth_url)
    url_obj = url_obj.replace_query_params(
        redirect_uri=get_redirect_uri(idp_name),
        **kwargs,
    )
    log.debug(f'redirect_to_idp(): {url_obj}')
    response = starlette.responses.RedirectResponse(
        url_obj,
        # RedirectResponse returns 307 temporary redirect by default
        status_code=starlette.status.HTTP_302_FOUND,
    )
    response.set_cookie(key='target', value=target_url)
    return response


def redirect(base_url: str, **kwargs):
    """Create a Starlette response that redirects to the base_url with query parameters"""
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
    """Create a Starlette response that redirects to the final target specified by the
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


def get_redirect_uri(idp_name):
    url_obj = starlette.datastructures.URL(Config.SERVICE_BASE_URL)
    return url_obj.replace(path=f'{url_obj.path}/callback/{idp_name}')


async def split_full_name(full_name: str) -> typing.Tuple[str, str | None]:
    """Split a full name into given name and family name.

    :returns: A tuple of given_name, family_name. If the full name is a single word,
        family_name will be None.
    """
    return full_name.split(' ', 1) if ' ' in full_name else (full_name, None)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)

    # def decode(self, obj):
    #     if isinstance(obj, datetime.datetime):
    #         return obj.isoformat()
    #     return super().default(obj)


def to_pretty_json(obj: list | dict) -> str:
    json_str = json.dumps(obj, indent=2, sort_keys=True, cls=CustomJSONEncoder)
    # print(json_str)
    return json_str


# def json_loads(json_str: str) -> list | dict:
#     return json.loads(json_str, cls=CustomJSONEncoder)


def from_json(json_str: str) -> list | dict:
    return json.loads(json_str)


def pp(obj: list | dict):
    print(pformat(obj))


def pformat(obj: list | dict):
    return pprint.pformat(obj, indent=2, sort_dicts=True)


# Avatars


def save_avatar(avatar_img: bytes, namespace_str: str, id_str: str, ext=None):
    """Save the avatar image to the filesystem and return the path to the file."""
    avatar_path = get_avatar_path(namespace_str, id_str, ext)
    avatar_path.parent.mkdir(parents=True, exist_ok=True)
    avatar_path.write_bytes(avatar_img)
    return avatar_path


def get_avatar_path(namespace_str, id_str, ext=None):
    avatar_path = (
        Config.AVATARS_PATH
        / namespace_str
        / filesystem.get_safe_reversible_path_element(id_str)
    )
    if ext:
        avatar_path = avatar_path.with_suffix(ext)
    return avatar_path


def get_profile_avatar_url(profile_row, refresh=False):
    """Return the URL to the avatar image for the given IdP and UID."""
    if not profile_row.has_avatar:
        return get_initials_avatar_url(profile_row.initials)
    avatar_url = url(
        '/'.join(
            (
                Config.AVATARS_URL,
                'profile',
                urllib.parse.quote(
                    filesystem.get_safe_reversible_path_element(profile_row.urid)
                ),
            )
        )
    )
    if refresh:
        timestamp = int(datetime.datetime.now().timestamp())
        avatar_url = avatar_url.include_query_params(refresh=timestamp)
    return avatar_url


def get_identity_avatar_url(identity_row, refresh=False):
    """Return the URL to the avatar image for the given IdP and UID."""
    if not identity_row.has_avatar:
        return get_anon_avatar_url()
    avatar_url = url(
        '/'.join(
            (
                Config.AVATARS_URL,
                identity_row.idp_name,
                urllib.parse.quote(
                    filesystem.get_safe_reversible_path_element(identity_row.uid)
                ),
            )
        )
    )
    if refresh:
        timestamp = int(datetime.datetime.now().timestamp())
        avatar_url = avatar_url.include_query_params(refresh=timestamp)
    return avatar_url


def get_anon_avatar_url():
    """Return the URL to the avatar image with the given initials."""
    return url(f'/static/svg/edi-anon-avatar.svg')


def get_initials_avatar_url(initials: str):
    """Return the URL to the avatar image with the given initials."""
    return url(f'/avatar/gen/{initials}')


def get_initials_avatar_path(initials: str):
    """Return the path to the avatar image with the given initials.

    If the avatar image does not exist, generate it and save it to the filesystem.
    """
    initials_avatar_path = get_avatar_path('initials', initials, '.png')
    if initials_avatar_path.exists():
        return initials_avatar_path
    avatar_img = generate_initials_avatar(initials)
    return save_avatar(avatar_img, 'initials', initials, '.png')


def generate_initials_avatar(initials: str):
    """Generate an avatar image with the given initials."""
    image = PIL.Image.new(
        'RGBA', (Config.AVATAR_WIDTH, Config.AVATAR_HEIGHT), Config.AVATAR_BG_COLOR
    )
    draw = PIL.ImageDraw.Draw(image)

    x1, y1, x2, y2 = draw.textbbox((0, 0), initials, font=AVATAR_FONT)

    text_width = x2 - x1
    text_height = y2 - y1
    text_x = (Config.AVATAR_WIDTH - text_width) // 2
    text_y = (Config.AVATAR_HEIGHT - text_height) // 2

    # y1 of the bounding box is not returned at 0, so we adjust here.
    text_y -= y1

    draw.text(
        (text_x, text_y), initials, fill=Config.AVATAR_TEXT_COLOR, font=AVATAR_FONT
    )

    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    # buffer.seek(0)

    return buffer.getvalue()


#


def get_idp_logo_url(idp_name: str):
    """Return the URL to the logo image for the given IdP."""
    return f'/static/idp-logos/{idp_name}.svg'


# Templates

templates = starlette.templating.Jinja2Templates(Config.TEMPLATES_PATH)
templates.env.globals.update(
    {
        # Make the url() function available in all templates
        'url': url,
        # Parameters for base.html
        'dev_menu': Config.ENABLE_DEV_MENU,
    }
)
