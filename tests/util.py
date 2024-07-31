import config
import pasta_token
import webapp.util

def create_test_pasta_token(urid, user_db_populated):
    profile = user_db_populated.get_profile(urid)
    return pasta_token.make_pasta_token(profile.urid)

    # profile = query.filter(Profile.urid == urid).first()

    # token = pasta_token.PastaToken()
    # token.system = config.Config.SYSTEM
    # token.uid = profile.urid
    # token.groups = ['public']
    # private_key = pasta_crypto.import_key(Config.PRIVATE_KEY_PATH)
    # log.debug(f'Creating token: {token.to_string()}')
    # auth_token = pasta_crypto.create_auth_token(private_key, token.to_string())
    # return auth_token


# def make_pasta_token(uid, groups=''):
#     token = PastaToken()
#     token.system = Config.SYSTEM
#     token.uid = uid
#     token.groups = groups
#     private_key = pasta_crypto.import_key(Config.PRIVATE_KEY_PATH)
#     log.debug(f'Creating token: {token.to_string()}')
#     auth_token = pasta_crypto.create_auth_token(private_key, token.to_string())
#     return auth_token



def get_db_as_json(user_db_populated):
    profile_list = []
    for profile_row in user_db_populated.get_all_profiles():
        profile_list.append(profile_row.as_dict())
    return webapp.util.to_pretty_json(profile_list)
