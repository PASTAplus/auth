"""Cache profiles and groups in memory for fast searching.

We dynamically update search results as the user types in the search box. In order to speed up this
search and avoid hitting the database each time the user presses a key, we cache the profiles and
groups in memory.
"""
import re

import daiquiri

import db.iface
import util.avatar
from config import Config

log = daiquiri.getLogger(__name__)

cache = {
    'sync_ts': None,
    'profile_list': [],
    'group_list': [],
}


async def init_cache():
    udb = db.iface.get_udb()
    cache['sync_ts'] = udb.get_sync_ts()
    await init_profiles(udb)
    await init_groups(udb)
    # pprint.pp(cache)


async def init_profiles(udb):
    profile_list = cache['profile_list']
    profile_list.clear()
    for profile_row in udb.get_all_profiles_generator():
        key_tup = (
            profile_row.full_name,
            profile_row.family_name,
            profile_row.email,
            profile_row.pasta_id,
            # Enable searching for the PASTA ID without the 'PASTA-' prefix
            re.sub(r'^PASTA-', '', profile_row.pasta_id),
        )
        profile_list.append(
            (
                tuple(k.lower() for k in key_tup if k is not None),
                {
                    'principal_id': profile_row.id,
                    'principal_type': 'profile',
                    'pasta_id': profile_row.pasta_id,
                    'title': profile_row.full_name,
                    'description': profile_row.email,
                    'avatar_url': profile_row.avatar_url,
                },
            )
        )


async def init_groups(udb):
    group_list = cache['group_list']
    group_list.clear()
    for group_row in udb.get_all_groups_generator():
        key_tup = (
            group_row.name,
            group_row.description,
            group_row.pasta_id,
            re.sub(r'^PASTA-', '', group_row.pasta_id),
            'group',
        )
        group_list.append(
            (
                tuple(k.lower() for k in key_tup if k is not None),
                {
                    'principal_id': group_row.id,
                    'principal_type': 'group',
                    'pasta_id': group_row.pasta_id,
                    'title': group_row.name,
                    'description': (group_row.description or '')
                    + f' (Owner: {group_row.profile.full_name})'.strip(),
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
    sync_ts = db.iface.get_udb().get_sync_ts()
    if sync_ts != cache.get('sync_ts'):
        await init_cache()

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
