#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: test_ldap

:Synopsis:

:Author:
    servilla
  
:Created:
    5/15/2019
"""
import os
import sys
import unittest

import daiquiri

from webapp.config import Config
from webapp import pasta_ldap

sys.path.insert(0, os.path.abspath('../webapp'))
logger = daiquiri.getLogger(__name__)


class TestPastaLdap(unittest.TestCase):

    def setUp(self):
        self._dn = Config.TEST_USER_DN
        self._bad_o = Config.TEST_USER_BAD_O
        self._bad_uid = Config.TEST_USER_BAD_UID
        self._password = Config.TEST_USER_PW

    def tearDown(self):
        pass

    def test_bind(self):
        self.assertTrue(pasta_ldap.bind(self._dn, self._password))
        self.assertFalse(pasta_ldap.bind(self._bad_o, self._password))
        self.assertFalse(pasta_ldap.bind(self._bad_uid, self._password))


if __name__ == '__main__':
    unittest.main()
