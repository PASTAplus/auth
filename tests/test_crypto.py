""":Mod: test_crypto

:Synopsis:

:Author:
    servilla
  
:Created:
    5/16/19
"""
import os
import sys

import daiquiri
import Crypto.PublicKey.RSA

from webapp.config import Config
from webapp import pasta_crypto

sys.path.insert(0, os.path.abspath("../src"))
log = daiquiri.getLogger(__name__)


def test_public_key():
    key = pasta_crypto.import_key(Config.PUBLIC_KEY)
    assert isinstance(key, Crypto.PublicKey.RSA.RsaKey)


def test_private_key():
    key = pasta_crypto.import_key(Config.PRIVATE_KEY)
    assert isinstance(key, Crypto.PublicKey.RSA.RsaKey)


def test_verify_auth_token():
    public_key = pasta_crypto.import_key(Config.PUBLIC_KEY)
    auth_token = Config.TEST_AUTH_TOKEN
    pasta_crypto.verify_auth_token(public_key, auth_token)


def test_create_auth_token():
    private_key = pasta_crypto.import_key(Config.PRIVATE_KEY)
    token = Config.TEST_TOKEN
    auth_token = pasta_crypto.create_auth_token(private_key, token)
    assert isinstance(auth_token, str)
