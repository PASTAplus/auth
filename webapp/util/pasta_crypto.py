import base64

import Crypto.Hash.MD5
import Crypto.PublicKey.RSA
import Crypto.Signature.pkcs1_15
import daiquiri

log = daiquiri.getLogger(__name__)


def import_key(f: str) -> Crypto.PublicKey.RSA.RsaKey:
    with open(f, 'r') as f:
        key_file = f.read()
    key = Crypto.PublicKey.RSA.import_key(key_file)
    return key


def verify_auth_token(public_key: Crypto.PublicKey.RSA.RsaKey, auth_token: str):
    """
    Verifies the PASTA+ authentication token, which is a two part string separate with a hyphen '-',
    where each part is base64 encoded:

        base64(token)-base64(md5_signature_of_base64_token)

    The base64 decoded token is a PASTA+ custom string like:

        uid=EDI,o=EDI,dc=edirepository,dc=org*https://pasta.edirepository.org/
        authentication*1558090703946*authenticated
    """
    token, signature = auth_token.split('-')
    h = Crypto.Hash.MD5.new(token.encode('utf-8'))
    signature = base64.b64decode(signature)
    Crypto.Signature.pkcs1_15.new(public_key).verify(h, signature)


def create_auth_token(private_key: Crypto.PublicKey.RSA.RsaKey, token: str) -> str:
    token = base64.b64encode(token.encode('utf-8'))
    h = Crypto.Hash.MD5.new(token)
    signature = base64.b64encode(Crypto.Signature.pkcs1_15.new(private_key).sign(h))
    auth_token = token.decode('utf-8') + '-' + signature.decode('utf-8')
    return auth_token
