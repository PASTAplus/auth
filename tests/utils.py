import logging
import re

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


def assert_edi_id_format(edi_id):
    """Check that the given value is in the form of an EDI-ID."""
    assert re.match(r'EDI-[\da-f]{32}$', edi_id)


async def assert_edi_id_in_db(edi_id, populated_dbi):
    """Check that the given EDI-ID exists in the DB"""
    await assert_edi_id_format(edi_id)
    profile_row = await populated_dbi.get_profile(edi_id)
    assert profile_row, f'Profile "{edi_id}" not found in the database.'


def get_db_as_json(populated_dbi):
    profile_list = []
    for profile_row in populated_dbi.get_all_profiles():
        profile_list.append(profile_row.as_dict())
    return util.pretty.to_pretty_json(profile_list)


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


def dump_response(response):
    log.info('#'* 30 + 'RESPONSE' + '#' * 30)
    log.info('Status code: %s', response.status_code)
    log.info('Headers: %s', response.headers)
    dump_json_with_syntax_highlighting(response.text)



def dump_json_with_syntax_highlighting(json_str):
    """Print a colored JSON representation of the object to the console."""
    import rich.console
    import rich.json
    highlighted_json_str = rich.json.JSON(json_str, indent=2)
    rich.console.Console().print(highlighted_json_str)

