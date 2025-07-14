import daiquiri
import pytest

from config import Config
from util import pasta_ldap

log = daiquiri.getLogger(__name__)

# Requires a running LDAP server with the test user configured
@pytest.mark.skip
def test_bind():
    assert pasta_ldap.bind(Config.TEST_USER_DN, Config.TEST_USER_PW)
    assert not pasta_ldap.bind(Config.TEST_USER_BAD_O, Config.TEST_USER_PW)
    assert not pasta_ldap.bind(Config.TEST_USER_BAD_UID, Config.TEST_USER_PW)
