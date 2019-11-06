#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: test_token

:Synopsis:

:Author:
    servilla
  
:Created:
    5/20/19
"""
import os
import sys
import unittest

import daiquiri

from webapp.config import Config
from webapp.pasta_token import PastaToken

sys.path.insert(0, os.path.abspath('../src'))
logger = daiquiri.getLogger('test_token: ' + __name__)


class TestToken(unittest.TestCase):

    def setUp(self):
        self._dn = Config.TEST_USER_DN
        self._token = Config.TEST_TOKEN

    def tearDown(self):
        pass

    def test_create_token(self):
        token = PastaToken()
        token.uid = self._dn
        token.system = Config.SYSTEM
        token.groups = Config.VETTED
        print(token.to_string())
        self.assertTrue(self._dn in token.to_string())

    def test_token_from_string(self):
        token = PastaToken()
        token.from_string(self._token)
        print(token.to_string())
        self.assertEqual(self._token, token.to_string())

    def test_token_ttl(self):
        token = PastaToken()
        token.uid = Config.PUBLIC
        token.system = Config.SYSTEM
        print(token.to_string())
        print(token.ttl_to_iso())
        self.assertTrue(token.is_valid_ttl())

    def test_token_from_auth_token(self):
        token = PastaToken()
        token.from_auth_token(Config.TEST_AUTH_TOKEN)
        print(token.to_string())
        self.assertEqual(self._token, token.to_string())


if __name__ == '__main__':
    unittest.main()