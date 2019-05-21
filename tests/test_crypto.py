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
import unittest

import daiquiri
import Crypto.PublicKey.RSA

from webapp.config import Config
from webapp import pasta_crypto

sys.path.insert(0, os.path.abspath('../src'))
logger = daiquiri.getLogger('test_crypto: ' + __name__)


class TestPastaCryptp(unittest.TestCase):

    def setUp(self):
        self._public_key = Config.PUBLIC_KEY
        self._private_key = Config.PRIVATE_KEY

    def tearDown(self):
        pass

    def testPublicKey(self):
        key = pasta_crypto.import_key(self._public_key)
        self.assertIsInstance(key, Crypto.PublicKey.RSA.RsaKey)

    def testPrivateKey(self):
        key = pasta_crypto.import_key(self._private_key)
        self.assertIsInstance(key, Crypto.PublicKey.RSA.RsaKey)

    def testVerifyAuthtoken(self):
        public_key = pasta_crypto.import_key(self._public_key)
        authtoken = Config.TEST_AUTH_TOKEN
        pasta_crypto.verify_authtoken(public_key, authtoken)

    def testCreateAuthtoken(self):
        private_key = pasta_crypto.import_key(self._private_key)
        token = Config.TEST_TOKEN
        authtoken = pasta_crypto.create_authtoken(private_key, token)
        self.assertIsInstance(authtoken, str)


if __name__ == '__main__':
    unittest.main()