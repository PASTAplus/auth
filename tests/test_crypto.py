"""Tests for the pasta_crypto module."""

import Crypto.PublicKey.RSA
import daiquiri

from config import Config
from util import pasta_crypto

log = daiquiri.getLogger(__name__)


def test_public_key():
    key = pasta_crypto.import_key(Config.PASTA_TOKEN_PUBLIC_KEY_PATH)
    assert isinstance(key, Crypto.PublicKey.RSA.RsaKey)


def test_private_key():
    key = pasta_crypto.import_key(Config.PASTA_TOKEN_PRIVATE_KEY_PATH)
    assert isinstance(key, Crypto.PublicKey.RSA.RsaKey)


def test_verify_auth_token():
    public_key = pasta_crypto.import_key(Config.PASTA_TOKEN_PUBLIC_KEY_PATH)
    auth_token = Config.TEST_AUTH_TOKEN
    pasta_crypto.verify_auth_token(public_key, auth_token)


def test_create_auth_token():
    private_key = pasta_crypto.import_key(Config.PASTA_TOKEN_PRIVATE_KEY_PATH)
    token = Config.TEST_TOKEN
    auth_token = pasta_crypto.create_auth_token(private_key, token)
    assert isinstance(auth_token, str)
