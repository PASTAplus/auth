import re

import daiquiri
import thefuzz.process

import db.iface
from config import Config

log = daiquiri.getLogger(__name__)

fuzz_cache = {}


async def init_cache():
    profile_list = db.iface.get_udb().get_all_profiles()
    for profile_row in profile_list:
        await add(profile_row)


async def add(profile_row):
    key = ' '.join(
        [
            profile_row.full_name,
            profile_row.email or '',
            profile_row.organization or '',
            profile_row.association or '',
        ],
    )
    fuzz_cache[re.sub(r'\s+', ' ', key)] = profile_row.id


async def remove_by_id(profile_row_id):
    for k, v in fuzz_cache.items():
        if v == profile_row_id:
            del fuzz_cache[k]


async def update(profile_row):
    await remove_by_id(profile_row.id)
    await add(profile_row)


async def search(query_str):
    match_list = thefuzz.process.extractBests(
        query_str, fuzz_cache.keys(), score_cutoff=Config.FUZZ_CUTOFF, limit=Config.FUZZ_LIMIT
    )
    log.debug(f'match_list:')
    for m in match_list:
        log.debug(f'  {m}')

    return [fuzz_cache[k] for k, v in match_list]

