import logging

import sqlalchemy

import db.models.profile
import util.pasta_jwt
import util.pasta_jwt
import util.pretty

log = logging.getLogger(__name__)


async def create_test_edi_token(edi_id, populated_dbi):
    # print(await get_edi_ids(populated_dbi))
    profile_row = await populated_dbi.get_profile(edi_id)
    if profile_row is None:
        raise ValueError(f'Profile "{edi_id}" not found in the database.')
    return await util.pasta_jwt.make_jwt(populated_dbi, profile_row.identities[0])


async def get_edi_ids(populated_dbi):
    """Get all profiles in the database."""
    result = await populated_dbi.session.execute(sqlalchemy.select(db.models.profile.Profile))
    return result.scalars().all()


# def get_db_as_json(populated_dbi):
#     profile_list = []
#     for profile_row in populated_dbi.get_all_profiles():
#         profile_list.append(profile_row.as_dict())
#     return util.to_pretty_json(profile_list)

async def make_jwt(dbi, profile_row):
    """Create a test JWT for the given profile.
    The returned JWT is sufficient for testing, but does not include the Identity fields and some
    other fields that are normally present.
    """
    principals_set = await dbi.get_equivalent_principal_edi_id_set(profile_row)
    principals_set.remove(profile_row.edi_id)
    pasta_jwt = util.pasta_jwt.PastaJwt(
        {
            'sub': profile_row.edi_id,
            'cn': profile_row.common_name,
            'email': profile_row.email,
            'principals': principals_set,
            'isEmailEnabled': profile_row.email_notifications,
            'isEmailVerified': False,
            'identityId': -1,
            'idpName': 'testIdp',
            'idpUid': 'testIdpUid',
            'idpCname': 'testIdpCname',
        }
    )
    # log.info('Created PASTA JWT:')
    # log.info(pasta_jwt.claims_pp)
    return pasta_jwt.encode()
