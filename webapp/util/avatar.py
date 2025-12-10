import db.models.profile
import pathlib
import contextlib
import io
import shutil

import PIL
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import filelock

import util.filesystem
import util.url
from config import Config

AVATAR_FONT = PIL.ImageFont.truetype(
    Config.AVATAR_FONT_PATH,
    Config.AVATAR_HEIGHT * Config.AVATAR_FONT_HEIGHT,
)


def save_avatar(avatar_img: bytes, namespace_str: str, id_str: str, ext=None):
    """Save an avatar image to the filesystem."""
    with _locked_avatar_path(namespace_str, id_str, ext) as avatar_path:
        avatar_path.write_bytes(avatar_img)


async def get_profile_avatar_url(dbi, profile_row):
    """Return the URL to the avatar image for the given profile."""
    # If this is a skeleton profile, we unconditionally return the anonymous avatar.
    if profile_row.idp_name == db.models.profile.IdpName.SKELETON:
        return get_anon_avatar_url()
    # We allow one level of indirection for the avatar image, to support the case where the user has
    # chosen to use the avatar from one of their linked profiles.
    if profile_row.avatar_profile_id is not None:
        # This profile is guaranteed to exist due to foreign key constraint.
        profile_row = await dbi.get_profile_by_id(profile_row.avatar_profile_id)
    # If the user has chosen to use the anonymous avatar, or this profile (or the referenced linked
    # profile) does not have an avatar, return the initials avatar URL.
    if profile_row.anonymous_avatar or not profile_row.avatar_ver:
        initials_str = get_profile_initials(profile_row)
        return get_initials_avatar_url(initials_str)
    # Otherwise, return the URL to the profile avatar image.
    return str(
        util.url.url(
            '/'.join(
                (
                    Config.AVATARS_URL,
                    _get_safe_rel_path('profile', profile_row.edi_id).as_posix(),
                )
            ),
            v=profile_row.avatar_ver,
        )
    )


def get_profile_avatar_url_for_select(profile_row):
    """Return the URL to the avatar image for the given profile, without resolving avatar_profile_id.
    - This is used when displaying a list of profiles for the user to select from.
    - If the profile has no avatar, return None.
    """
    if not profile_row.avatar_ver:
        return None
    return str(
        util.url.url(
            '/'.join(
                (
                    Config.AVATARS_URL,
                    _get_safe_rel_path('profile', profile_row.edi_id).as_posix(),
                )
            ),
            v=profile_row.avatar_ver,
        )
    )


def get_anon_avatar_url():
    """Return the URL to the anonymous avatar."""
    return str(util.url.url(f'/static/svg/edi-anon-avatar.svg'))


def get_initials_avatar_url(initials_str: str):
    """Return the URL to the avatar image with the given initials.
    - This returns an API endpoint which will generate and cache the avatar image if it does not
    exist.
    """
    return str(util.url.url(f'/ui/api/avatar/gen/{util.url.urlenc(initials_str)}'))


def get_initials_avatar_path(initials_str: str):
    """Return the path to the avatar image with the given initials.
    - If the avatar image does not exist, first generate it and save it to the filesystem.
    """
    with _locked_avatar_path('initials', initials_str, '.png') as avatar_path:
        if avatar_path.exists():
            return avatar_path
        avatar_img = _generate_initials_avatar(initials_str)
        avatar_path.write_bytes(avatar_img)
        return avatar_path


def get_profile_initials(profile_row):
    """Get the user's initials for the given profile."""
    if profile_row.common_name:
        part_tup = profile_row.common_name.split()
        if len(part_tup) > 3:
            part_tup = part_tup[0], part_tup[1], part_tup[-1]
        return ''.join(s[0] for s in part_tup).upper()
    return '?'


def get_group_avatar_url():
    """Return the URL to the group avatar image."""
    return str(util.url.url(f'/static/svg/group.svg'))


def get_public_avatar_url():
    """Return the URL to the public avatar image."""
    return str(util.url.url(f'/static/svg/public.svg'))


def init_system_avatar(edi_id: str, asset_filename: str):
    """Create an avatar image for a system profile.
    - This copies the avatar image from the assets directory to the profile avatar directory.
    """
    with _locked_avatar_path('profile', edi_id) as avatar_path:
        src_path = Config.ASSETS_PATH / asset_filename
        shutil.copy(src_path, avatar_path)


def _generate_initials_avatar(initials_str):
    """Generate an avatar image with the given initials."""
    image = PIL.Image.new(
        'RGBA', (Config.AVATAR_WIDTH, Config.AVATAR_HEIGHT), Config.AVATAR_BG_COLOR
    )
    draw = PIL.ImageDraw.Draw(image)
    x1, y1, x2, y2 = draw.textbbox((0, 0), initials_str, font=AVATAR_FONT)
    text_width = x2 - x1
    text_height = y2 - y1
    text_x = (Config.AVATAR_WIDTH - text_width) // 2
    text_y = (Config.AVATAR_HEIGHT - text_height) // 2
    # Even though we're drawing text into a box at (0,0), y1 of the bounding box may not be returned
    # at 0, so we adjust here. This is probably due to the font having characters that are taller
    # than the characters used by the given initials.
    text_y -= y1
    draw.text((text_x, text_y), initials_str, fill=Config.AVATAR_TEXT_COLOR, font=AVATAR_FONT)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


@contextlib.contextmanager
def _locked_avatar_path(namespace_str, id_str, ext_str=None):
    avatar_path = Config.AVATARS_PATH / _get_safe_rel_path(namespace_str, id_str, ext_str)
    lock_path = avatar_path.with_suffix('.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with filelock.FileLock(lock_path):
        try:
            yield avatar_path
        finally:
            if lock_path.exists():
                lock_path.unlink()


def _get_safe_rel_path(namespace_str, id_str, ext_str=None):
    """Return a safe relative path for the given namespace and id."""
    path = pathlib.Path(namespace_str, util.filesystem.get_safe_reversible_path_element(id_str))
    if ext_str:
        path = path.with_suffix(ext_str)
    return path
