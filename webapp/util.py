import base64
import binascii
import datetime
import io
import json
import pprint
import re
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
import old_token
import pasta_jwt
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
    log_dict(log.debug, f'Redirecting (303) to: {url_str}', query_param_dict)
    return starlette.responses.RedirectResponse(
        starlette.datastructures.URL(url_str).replace_query_params(**query_param_dict),
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )


def redirect_to_idp(
    idp_auth_url: str,
    idp_name: str,
    target_url: str,
    **query_param_dict,
):
    """Create a Response that redirects to the IdP with which we will be authenticating,
    and include a cookie with the client's final target.
    """
    url_obj = starlette.datastructures.URL(idp_auth_url)
    url_obj = url_obj.replace_query_params(
        redirect_uri=get_redirect_uri(idp_name),
        **query_param_dict,
    )
    log.debug(f'redirect_to_idp(): {url_obj}')
    response = starlette.responses.RedirectResponse(
        url_obj,
        # RedirectResponse returns 307 Temporary Redirect by default
        status_code=starlette.status.HTTP_302_FOUND,
    )
    response.set_cookie(key='target', value=target_url)
    return response


def handle_successful_login(
    request,
    udb,  # db.iface.UserDb
    target_url: str,
    full_name,
    idp_name,
    uid,
    email,
    has_avatar,
    is_vetted,
):
    """After user has successfully authenticated:

    - Create or update user's Profile and Identity in the database
    - Create old style and new style tokens
    - Redirect to the final target URL, providing the tokens and other information
    """
    identity_row = udb.create_or_update_profile_and_identity(
        full_name, idp_name, uid, email, has_avatar
    )

    if idp_name == 'google':
        old_uid = email
    else:
        old_uid = uid

    old_token_ = old_token.make_old_token(
        uid=old_uid, groups=Config.VETTED if is_vetted else Config.AUTHENTICATED
    )
    pasta_token = pasta_jwt.make_jwt(udb, identity_row, is_vetted=is_vetted)

    return redirect_final(
        target_url,
        token=old_token_,
        pasta_token=pasta_token,
        urid=identity_row.profile.urid,
        full_name=identity_row.profile.full_name,
        email=identity_row.profile.email,
        uid=identity_row.uid,
        idp_name=identity_row.idp_name,
        sub=identity_row.uid,
        link_token=request.cookies.get('pasta_token'),
    )


def redirect_final(
    target_url: str,
    token: str,
    pasta_token: str,
    # TODO: All the following query parameters should be removed from the redirect
    # URI when the transition to the new authentication system is complete, since
    # they are effectively unsigned claims.
    urid: str,
    full_name: str,
    email: str,
    uid: str,
    idp_name: str,
    sub: str,
    link_token: str | None,
):
    """Create Response that redirects to the final target URL after successful
    authentication. This is the final step in the authentication process, and creates a
    uniform set of query parameters and cookies returned to all clients for all
    authentication flows.

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
        urid=urid,
        cname=full_name,
        email=email,
        uid=uid,
        idp_name=idp_name,
        # For ezEML
        sub=sub,
        # For account linking
        link_token=link_token if link_token else '',
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
    log_dict(log.debug, f'Redirecting (307) to: {url_str}', query_param_dict)
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


def log_dict(logger: typing.Callable, msg: str, d: dict):
    logger(f'{msg}:')
    for k, v in d.items():
        logger(f'  {k}: {v}')


def get_redirect_uri(idp_name):
    url_obj = starlette.datastructures.URL(Config.SERVICE_BASE_URL)
    return url_obj.replace(path=f'{url_obj.path}/callback/{idp_name}')


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


# LDAP


def get_ldap_uid(ldap_dn: str) -> str:
    dn_dict = {
        k.strip(): v.strip()
        for (k, v) in (part.split('=') for part in ldap_dn.split(','))
    }
    return dn_dict['uid']


def get_ldap_dn(uid: str) -> str:
    return f'uid={uid},o=EDI,dc=edirepository,dc=org'


def parse_authorization_header(
    request,
) -> tuple[str, str] | starlette.responses.Response:
    """Parse the Authorization header from a request and return (uid, pw). Raise
    ValueError on errors.
    """
    auth_str = request.headers.get('Authorization')
    if auth_str is None:
        raise ValueError('No authorization header in request')
    if not (m := re.match(r'Basic\s+(.*)', auth_str)):
        raise ValueError(
            f'Invalid authorization scheme. Only Basic is supported: {auth_str}'
        )
    encoded_credentials = m.group(1)
    try:
        decoded_credentials = base64.b64decode(
            encoded_credentials, validate=True
        ).decode('utf-8')
        uid, password = decoded_credentials.split(':', 1)
        return uid, password
    except (ValueError, IndexError, binascii.Error) as e:
        raise ValueError(f'Malformed authorization header: {e}')


def format_authorization_header(uid: str, password: str) -> str:
    return f'Basic {base64.b64encode(f"{uid}:{password}".encode()).decode()}'
