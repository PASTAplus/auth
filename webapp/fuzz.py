import re

import daiquiri
import thefuzz.process

import db.iface
from config import Config

log = daiquiri.getLogger(__name__)

fuzz_cache = {
    'sync_ts': None,
    'profile_dict': {}
}


async def init_cache():
    udb = db.iface.get_udb()
    fuzz_cache['sync_ts'] = udb.get_sync_ts()
    profile_dict = fuzz_cache['profile_dict']
    profile_dict.clear()
    for profile_row in udb.get_all_profiles_generator():
        key = ' '.join(
            [
                profile_row.full_name,
                profile_row.email or '',
                profile_row.organization or '',
                profile_row.association or '',
            ],
        )
        profile_dict[re.sub(r'\s+', ' ', key)] = profile_row.id


async def search(query_str):
    sync_ts = db.iface.get_udb().get_sync_ts()
    if sync_ts != fuzz_cache.get('sync_ts'):
        await init_cache()
    profile_dict = fuzz_cache['profile_dict']
    match_list = thefuzz.process.extractBests(
        query_str,
        profile_dict.keys(),
        score_cutoff=Config.FUZZ_CUTOFF,
        limit=Config.FUZZ_LIMIT,
    )
    # log.debug(f'match_list:')
    # for m in match_list:
    #     log.debug(f'  {m}')
    return [profile_dict[k] for k, v in match_list]
