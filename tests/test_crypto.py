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
        authtoken = 'dWlkPUVESSxvPUVESSxkYz1lZGlyZXBvc2l0b3J5LGRjPW9yZypodHRwczovL3Bhc3RhLmVkaXJlcG9zaXRvcnkub3JnL2F1dGhlbnRpY2F0aW9uKjE1NTgwOTA3MDM5NDYqYXV0aGVudGljYXRlZA==-yUoVTpyVityVkfqOpGSPosJYzndBMdwoUTGB0osuqyCNOouPxRllz/pRklaEWqi+faNLGHh8Dzh7qrtxTLLDs+MpBXudaJIIQep6PNnvEDgasrTvA9KV/vnKsyDnu4VaJnyuoKGRryP6PXlJs8UTXhtGpRf2vnTM/oifeRx0NB3y7aEv3Xn85ogxl0MaeyXJFeQMAAyN9ahYgJUC4jFgCqYlLj/x0PAlXwq2C/AwnjC/XJ2mxEQm1E/RMY9Z9EjHx+dSruXEs3wQiBbnus7BPvJR84zqEjl3EYpYwmYRkLViDHYoGdbegcDfuUfKv4y5Hun+r0ICNt09nBV4wci3TQ=='
        pasta_crypto.verify_authtoken(public_key, authtoken)

    def testCreateAuthtoken(self):
        private_key = pasta_crypto.import_key(self._private_key)
        token = 'uid=EDI,o=EDI,dc=edirepository,dc=org*https://pasta.edirepository.org/authentication*1558090703946*authenticated'
        authtoken = pasta_crypto.create_authtoken(private_key, token)
        self.assertIsInstance(authtoken, str)
        print(authtoken)


if __name__ == '__main__':
    unittest.main()