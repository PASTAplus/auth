import datetime
import io
import urllib.parse

import PIL
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

import util.filesystem
import util.utils

from config import Config


AVATAR_FONT = PIL.ImageFont.truetype(
    Config.AVATAR_FONT_PATH,
    Config.AVATAR_HEIGHT * Config.AVATAR_FONT_HEIGHT,
)


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
        / util.filesystem.get_safe_reversible_path_element(id_str)
    )
    if ext:
        avatar_path = avatar_path.with_suffix(ext)
    return avatar_path


def get_profile_avatar_url(profile_row, refresh=False):
    """Return the URL to the avatar image for the given IdP and idp_uid."""
    if not profile_row.has_avatar:
        return get_initials_avatar_url(profile_row.initials)
    avatar_url = util.utils.url(
        '/'.join(
            (
                Config.AVATARS_URL,
                'profile',
                urllib.parse.quote(
                    util.filesystem.get_safe_reversible_path_element(profile_row.pasta_id)
                ),
            )
        )
    )
    if refresh:
        timestamp = int(datetime.datetime.now().timestamp())
        avatar_url = avatar_url.include_query_params(refresh=timestamp)
    return avatar_url


def get_identity_avatar_url(identity_row, refresh=False):
    """Return the URL to the avatar image for the given IdP and idp_uid."""
    if not identity_row.has_avatar:
        return get_anon_avatar_url()
    avatar_url = util.utils.url(
        '/'.join(
            (
                Config.AVATARS_URL,
                identity_row.idp_name,
                urllib.parse.quote(
                    util.filesystem.get_safe_reversible_path_element(identity_row.idp_uid)
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
    return util.utils.url(f'/static/svg/edi-anon-avatar.svg')


def get_initials_avatar_url(initials: str):
    """Return the URL to the avatar image with the given initials."""
    return util.utils.url(f'/avatar/gen/{initials}')


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
