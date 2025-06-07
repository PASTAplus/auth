import sqlalchemy

import util.pasta_jwt

import db.models.profile

from config import Config


async def create_test_pasta_token(edi_id, pop_udb):
    # print(await get_edi_ids(pop_udb))
    profile_row = await pop_udb.get_profile(edi_id)
    if profile_row is None:
        raise ValueError(f"Profile '{edi_id}' not found in the database.")
    return await util.pasta_jwt.make_jwt(pop_udb, profile_row.identities[0], is_vetted=False)


async def get_edi_ids(pop_udb):
    """List all EDI-IDs in the database."""
    result = await pop_udb.session.execute(sqlalchemy.select(db.models.profile.Profile))
    return result.scalars().all()


# def make_pasta_token(uid, groups=''):
#     token = PastaToken()
#     token.system = Config.SYSTEM
#     token.uid = uid
#     token.groups = groups
#     private_key = pasta_crypto.import_key(Config.PRIVATE_KEY_PATH)
#     log.debug(f'Creating token: {token.to_string()}')
#     auth_token = pasta_crypto.create_auth_token(private_key, token.to_string())
#     return auth_token


# def get_db_as_json(pop_udb):
#     profile_list = []
#     for profile_row in pop_udb.get_all_profiles():
#         profile_list.append(profile_row.as_dict())
#     return util.to_pretty_json(profile_list)
