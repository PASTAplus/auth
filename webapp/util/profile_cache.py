"""Cache frequently used values for system profiles"""

import daiquiri

from config import Config


profile_cache = {}


log = daiquiri.getLogger(__name__)


async def get_public_access_profile_id(dbi):
    """Get the public access profile ID from the cache or database."""
    return await _get_system_profile(dbi, 'public', dbi.get_public_profile)


async def get_authenticated_access_profile_id(dbi):
    """Get the authenticated access profile row ID from the cache or database."""
    return await _get_system_profile(dbi, 'authenticated', dbi.get_authenticated_profile)


def is_superuser(profile_row):
    return profile_row.edi_id in Config.SUPERUSER_LIST


def is_public_access(profile_row):
    """Check if the profile is the public access profile."""
    return profile_row.edi_id == Config.PUBLIC_EDI_ID


def is_authenticated_access(profile_row):
    """Check if the profile is the authenticated access profile."""
    return profile_row.edi_id == Config.AUTHENTICATED_EDI_ID


async def _get_system_profile(dbi, key_str, get_profile_func):
    if key_str not in profile_cache:
        profile_row = await get_profile_func()
        profile_cache[key_str] = profile_row.id
    return profile_cache[key_str]
