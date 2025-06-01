"""Cache profiles and groups in memory for fast searching.

We dynamically update search results as the user types in the search box. In order to speed up this
search and avoid hitting the database each time the user presses a key, we cache the profiles and
groups in memory.
"""
import re

import daiquiri

import util.avatar
from config import Config
import util.dependency

log = daiquiri.getLogger(__name__)

cache = {
    'sync_ts': None,
    'profile_list': [],
    'group_list': [],
}


async def init_cache(udb):
    cache['sync_ts'] = await udb.get_sync_ts()
    await init_profiles(udb)
    await init_groups(udb)
    # pprint.pp(cache)


async def init_profiles(udb):
    profile_list = cache['profile_list']
    profile_list.clear()
    async for (profile_row, principal_row) in udb.get_all_profiles_generator():
        if profile_row.edi_id in Config.SUPERUSER_LIST:
            continue
        key_tup = (
            profile_row.common_name,
            profile_row.email,
            profile_row.edi_id,
            # Enable searching for the EDI-ID without the 'EDI-' prefix
            re.sub(r'^EDI-', '', profile_row.edi_id),
        )
        profile_list.append(
            (
                tuple(k.lower() for k in key_tup if k is not None),
                {
                    'profile_id': profile_row.id,
                    'principal_id': principal_row.id,
                    'principal_type': 'profile',
                    'edi_id': profile_row.edi_id,
                    'title': profile_row.common_name,
                    'description': profile_row.email,
                    'avatar_url': profile_row.avatar_url,
                },
            )
        )


async def init_groups(udb):
    group_list = cache['group_list']
    group_list.clear()
    async for group_row in udb.get_all_groups_generator():
        key_tup = (
            group_row.name,
            group_row.description,
            group_row.edi_id,
            re.sub(r'^EDI-', '', group_row.edi_id),
            'group',
        )
        group_list.append(
            (
                tuple(k.lower() for k in key_tup if k is not None),
                {
                    'principal_id': group_row.id,
                    'principal_type': 'group',
                    'edi_id': group_row.edi_id,
                    'title': group_row.name,
                    'description': (group_row.description or ''),
                    'avatar_url': str(util.avatar.get_group_avatar_url()),
                },
            )
        )


async def search(query_str, include_groups):
    """Search for profiles and groups based on the query string. A match is found if any of the
    search keys start with the query string.

    Matches are returned with profiles first, then groups. Within the profiles and groups, the order
    is determined by the order_by() statements in the profile and group generators.
    """
    async with util.dependency.get_udb() as udb:
        sync_ts = await udb.get_sync_ts()
        if sync_ts != cache.get('sync_ts'):
            await init_cache(udb)

    match_list = []

    # The keys are stored in lower case.
    lower_str = query_str.lower()
    for key_tup, principal_dict in cache['profile_list']:
        if len(match_list) >= Config.SEARCH_LIMIT:
            break
        if any(k.startswith(lower_str) for k in key_tup):
            match_list.append(principal_dict)

    if include_groups:
        for key_tup, principal_dict in cache['group_list']:
            if len(match_list) >= Config.SEARCH_LIMIT:
                break
            if any(k.startswith(lower_str) for k in key_tup):
                match_list.append(principal_dict)

    # log.debug(f'match_list:')
    # for m in match_list:
    #     log.debug(f'  {m}')

    return match_list
