#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
logger = daiquiri.getLogger("test_crypto: " + __name__)


def test_public_key():
    key = pasta_crypto.import_key(Config.PUBLIC_KEY)
    assert isinstance(key, Crypto.PublicKey.RSA.RsaKey)


def test_private_key():
    key = pasta_crypto.import_key(Config.PRIVATE_KEY)
    assert isinstance(key, Crypto.PublicKey.RSA.RsaKey)


def test_verify_authtoken():
    public_key = pasta_crypto.import_key(Config.PUBLIC_KEY)
    authtoken = Config.TEST_AUTH_TOKEN
    pasta_crypto.verify_authtoken(public_key, authtoken)


def test_create_authtoken():
    private_key = pasta_crypto.import_key(Config.PRIVATE_KEY)
    token = Config.TEST_TOKEN
    authtoken = pasta_crypto.create_authtoken(private_key, token)
    assert isinstance(authtoken, str)
