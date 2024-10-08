import os
import sys

import daiquiri

from webapp.config import Config
from webapp import pasta_ldap

# sys.path.insert(0, os.path.abspath("../webapp"))
log = daiquiri.getLogger(__name__)


def test_bind():
    assert pasta_ldap.bind(Config.TEST_USER_DN, Config.TEST_USER_PW)
    assert not pasta_ldap.bind(Config.TEST_USER_BAD_O, Config.TEST_USER_PW)
    assert not pasta_ldap.bind(Config.TEST_USER_BAD_UID, Config.TEST_USER_PW)
