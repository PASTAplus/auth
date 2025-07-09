import daiquiri
import pytest

from config import Config
from util import pasta_ldap

# sys.path.insert(0, os.path.abspath("../webapp"))
log = daiquiri.getLogger(__name__)

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(50),
]

def test_bind():
    assert pasta_ldap.bind(Config.TEST_USER_DN, Config.TEST_USER_PW)
    assert not pasta_ldap.bind(Config.TEST_USER_BAD_O, Config.TEST_USER_PW)
    assert not pasta_ldap.bind(Config.TEST_USER_BAD_UID, Config.TEST_USER_PW)
