import daiquiri

from config import Config
import util.old_token

log = daiquiri.getLogger(__name__)


def test_create_token():
    token = util.old_token.OldToken()
    token.uid = Config.TEST_USER_DN
    token.system = Config.SYSTEM
    token.groups = Config.VETTED
    print(token.to_string())
    assert Config.TEST_USER_DN in token.to_string()


def test_token_from_string():
    token = util.old_token.OldToken()
    token.from_string(Config.TEST_TOKEN)
    print(token.to_string())
    assert Config.TEST_TOKEN == token.to_string()


def test_token_ttl():
    token = util.old_token.OldToken()
    token.uid = Config.PUBLIC
    token.system = Config.SYSTEM
    print(token.to_string())
    print(token.ttl_to_iso())
    assert token.is_valid_ttl()


def test_token_from_auth_token():
    token = util.old_token.OldToken()
    token.from_auth_token(Config.TEST_AUTH_TOKEN)
    print(token.to_string())
    assert Config.TEST_TOKEN == token.to_string()
