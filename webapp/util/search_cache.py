"""Cache profiles and groups in memory for fast searching.

We dynamically update search results as the user types in the search box. In order to speed
up this search and avoid hitting the database, we cache the profiles and groups in memory.
"""
import pprint
import re

import daiquiri

import db.iface
from config import Config

log = daiquiri.getLogger(__name__)

cache = {
    'sync_ts': None,
    'candidate_list': [],
}


async def init_cache():
    udb = db.iface.get_udb()
    cache['sync_ts'] = udb.get_sync_ts()
    cache['candidate_list'].clear()
    await init_profiles(udb)
    await init_groups(udb)
    pprint.pp(cache)


async def init_profiles(udb):
    candidate_list = cache['candidate_list']
    for profile_row in udb.get_all_profiles_generator():
        key_tup = (
            profile_row.given_name,
            profile_row.family_name,
            profile_row.full_name,
            profile_row.email,
            profile_row.pasta_id,
        )
        candidate_list.append(
            (
                tuple(k.lower() for k in key_tup if k is not None),
                {
                    'id': profile_row.id,
                    'pasta_id': profile_row.pasta_id,
                    'title': profile_row.full_name,
                    'descr': profile_row.email,
                    'avatar_url': profile_row.avatar_url,
                    'type': 'profile',
                },
            )
        )


async def init_groups(udb):
    candidate_list = cache['candidate_list']
    for group_row in udb.get_all_groups_generator():
        key_tup = (
            group_row.name,
            group_row.description,
            group_row.pasta_id,
            # Enable searching for the PASTA ID without the 'PASTA-' prefix
            re.sub(r'^PASTA-', '', group_row.pasta_id),
        )
        candidate_list.append(
            (
                tuple(k.lower() for k in key_tup if k is not None),
                {
                    'id': group_row.id,
                    'pasta_id': group_row.pasta_id,
                    'title': group_row.name,
                    'descr': (group_row.description or '')
                    + f' (owner {group_row.profile.full_name})',
                    'avatar_url': group_row.profile.avatar_url,
                    'type': 'group',
                },
            )
        )


async def get_client_group_dict(group_row):
    return {}


async def search(query_str):
    sync_ts = db.iface.get_udb().get_sync_ts()
    if sync_ts != cache.get('sync_ts'):
        await init_cache()

    # score_gen = ((score(query_str, k), v) for k, v in )

    match_list = []

    for key_tup, v in cache['candidate_list']:
        if is_match(query_str, key_tup):
            match_list.append(v)
        if len(match_list) >= Config.SEARCH_LIMIT:
            break

    # log.debug(f'match_list:')
    # for m in match_list:
    #     log.debug(f'  {m}')

    return match_list


def get_score(query_str, key_tup):
    """Return the score of the query string against the key tuple.

    Strategy: Count the number of shared characters between query_str and each string in the
    key_tup, and score each matching character as 100. Then subtract the length of query_str in
    order to penalize strings with more non-matching characters.
    """
    return max(
        sum(100 for c1, c2 in zip(k, query_str) if c1 == c2) - len(query_str)
        for k in key_tup
        if k is not None
    )


def is_match(query_str, key_tup):
    """Return True if one or more of the key_tup strings start with the query_str."""
    return any(k.startswith(query_str) for k in key_tup if k is not None)
