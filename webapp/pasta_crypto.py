#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: pasta_crypto

:Synopsis:

:Author:
    servilla

:Created:
    5/16/19
"""
import base64

from Crypto.Hash import MD5
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
import daiquiri

logger = daiquiri.getLogger("pasta_crypto: " + __name__)


def import_key(f: str) -> tuple:
    with open(f, "r") as f:
        key_file = f.read()
    key = RSA.import_key(key_file)
    return key


def verify_authtoken(public_key: RSA.RsaKey, auth_token: str):
    """
    Verifies the PASTA+ authentication token, which is a two part string
    separate with a hyphen '-', and each part being base64 encoded:

        base64(token)-base64(md5_signature_of_base64_token)

    The base64 decoded token is a PASTA+ custom string like:

        uid=EDI,o=EDI,dc=edirepository,dc=org*https://pasta.edirepository.org/
        authentication*1558090703946*authenticated

    :param pub_key:
    :param auth_token:
    :return:
    """
    token, signature = auth_token.split("-")
    h = MD5.new(token.encode("utf-8"))
    signature = base64.b64decode(signature)
    pkcs1_15.new(public_key).verify(h, signature)


def create_authtoken(private_key: RSA.RsaKey, token: str) -> str:
    token = base64.b64encode(token.encode("utf-8"))
    h = MD5.new(token)
    signature = base64.b64encode(pkcs1_15.new(private_key).sign(h))
    authtoken = token.decode("utf-8") + "-" + signature.decode("utf-8")
    return authtoken


def main():
    return 0


if __name__ == "__main__":
    main()
