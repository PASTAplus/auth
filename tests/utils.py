import datetime
import logging
import pathlib
import re

import jwt
import sqlalchemy
import sqlalchemy.exc

import db.models.profile
import util.edi_token
import util.pretty
from config import Config

HERE_PATH = pathlib.Path(__file__).parent.resolve()
TEST_FILES_PATH = HERE_PATH / 'test_files'
PRIVATE_KEY_STR = Config.JWT_PRIVATE_KEY_PATH.read_text()

log = logging.getLogger(__name__)


async def create_test_edi_token(edi_id, populated_dbi):
    profile_row = await populated_dbi.get_profile(edi_id)
    return await util.edi_token.create(populated_dbi, profile_row.identities[0])


async def get_edi_ids(populated_dbi):
    """Get all profiles in the database."""
    result = await populated_dbi.session.execute(sqlalchemy.select(db.models.profile.Profile))
    return result.scalars().all()


def assert_edi_id_format(edi_id):
    """Check that the given value is in the form of an EDI-ID."""
    assert re.match(r'EDI-[\da-f]{32}$', edi_id)


async def assert_edi_id_in_db(edi_id, populated_dbi):
    """Check that the given EDI-ID exists in the DB"""
    assert_edi_id_format(edi_id)
    await populated_dbi.get_profile(edi_id)


def get_db_as_json(populated_dbi):
    profile_list = []
    for profile_row in populated_dbi.get_all_profiles():
        profile_list.append(profile_row.as_dict())
    return util.pretty.to_pretty_json(profile_list)


async def make_edi_token(dbi, profile_row):
    """Create a test JWT for the given profile.
    The returned JWT is sufficient for testing, but does not include the IdP fields and some other
    fields that are normally present.
    """
    return await util.edi_token.create_by_profile(dbi, profile_row)


def dump_response(response):
    log.info('#' * 30 + 'RESPONSE' + '#' * 30)
    log.info('Status code: %s', response.status_code)
    log.info('Headers: %s', response.headers)
    dump_json_with_syntax_highlighting(response.text)


def dump_json_with_syntax_highlighting(json_str):
    """Print a colored JSON representation of the object to the console."""
    import rich.json

    highlighted_json_str = rich.json.JSON(json_str, indent=2)
    rich.console.Console().print(highlighted_json_str)


def load_test_file(filename):
    """Load a test file from the test_files directory."""
    return (TEST_FILES_PATH / filename).read_text()


async def add_vetted(populated_dbi, service_profile_row, profile_row):
    """Add the given profile to the Vetted system group."""
    if await populated_dbi.is_vetted(profile_row):
        return
    await populated_dbi.add_group_member(
        service_profile_row, (await populated_dbi.get_vetted_group()).id, profile_row.id
    )
    await populated_dbi.flush()
