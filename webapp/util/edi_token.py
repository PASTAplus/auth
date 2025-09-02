"""Encode and decode EDI Tokens.
- EDI Tokens are JSON Web Token (JWTs). A JWT consists of a header, a JSON paylod, and a signature.
These are Base64URL encoded and combined into a single string with the parts separated by dots.
- The header specifies the algorithm used to sign the token, and other metadata.
- The payload contains the claims, which are statements about a user profile, and metadata about the
token itself.
- The signature ensures that the token was created by EDI and has not been modified.
"""

import dataclasses
import datetime
import pprint

import daiquiri
import jwt
import sqlalchemy.exc

import db.models.identity
from config import Config

log = daiquiri.getLogger(__name__)

PRIVATE_KEY_STR = Config.JWT_PRIVATE_KEY_PATH.read_text()
PUBLIC_KEY_STR = Config.JWT_PUBLIC_KEY_PATH.read_text()


@dataclasses.dataclass
class EdiTokenClaims:
    """Hold the claims of an EDI JWT.
    - We use this instead of the plain dict that represents the JSON in a decoded JWT in order to
    formalize the claims. This also enables convenient access via attributes, and helps the IDE with
    autocomplete, syntax checking, etc.
    """

    def __post_init__(self):
        now_dt = datetime.datetime.now(datetime.UTC)
        self.iat = self.iat or int(now_dt.timestamp())
        self.nbf = self.nbf or int(now_dt.timestamp())
        self.exp = self.exp or int((now_dt + Config.JWT_EXPIRATION_DELTA).timestamp())

    sub: str
    cn: str
    email: str
    principals: set[str] = dataclasses.field(default_factory=set)
    isEmailEnabled: bool = False
    isEmailVerified: bool = False
    identityId: int | None = None
    idpName: str | None = None
    idpUid: str | None = None
    idpCname: str | None = None
    iss: str = Config.JWT_ISSUER
    hd: str = Config.JWT_HOSTED_DOMAIN
    iat: int | None = None
    nbf: int | None = None
    exp: int | None = None
    link: dict | None = None

    @property
    def edi_id(self):
        return self.sub


async def create(dbi, identity_row, link_claims: dict | None = None) -> str:
    """Create an EDI JSON Web Token (JWT).
    link_claims: Claims temporarily holding account information during an account linking procedure.
    """
    profile_row = identity_row.profile
    principals_set: set = await dbi.get_equivalent_principal_edi_id_set(profile_row)
    principals_set.discard(profile_row.edi_id)
    claims_obj = EdiTokenClaims(
        sub=profile_row.edi_id,
        cn=profile_row.common_name,
        email=profile_row.email,
        principals=principals_set,
        isEmailEnabled=profile_row.email_notifications,
        isEmailVerified=False,
        identityId=identity_row.id,
        idpName=identity_row.idp_name.name.lower(),
        idpUid=(
            identity_row.email
            if identity_row.idp_name == db.models.identity.IdpName.GOOGLE
            else identity_row.idp_uid
        ),
        idpCname=identity_row.common_name,
        link=link_claims,
    )
    return _create(claims_obj)


async def create_by_profile(dbi, profile_row):
    """Create an EDI JSON Web Token (JWT) by the given profile.
    - The normal create() method takes an Identity in order to include information about which
    account was used for the current sign in to the profile. In some cases, we don't have identity
    information, but we can still create a JWT with just profile information.
    """
    principals_set = await dbi.get_equivalent_principal_edi_id_set(profile_row)
    principals_set.discard(profile_row.edi_id)
    claims_obj = EdiTokenClaims(
        sub=profile_row.edi_id,
        cn=profile_row.common_name,
        email=profile_row.email,
        principals=principals_set,
    )
    return _create(claims_obj)


def create_by_claims(**claims_dict):
    return _create(EdiTokenClaims(**claims_dict))


def _create(claims_obj) -> str:
    log.info('Created PASTA JWT:')
    log.info(claims_pformat(claims_obj))
    claims_dict = claims_obj.__dict__.copy()
    claims_dict['principals'] = list(sorted(claims_dict['principals']))
    log.info(f'Encoding token: {claims_dict}')
    return jwt.encode(claims_dict, PRIVATE_KEY_STR, algorithm=Config.JWT_ALGORITHM)


async def decode(dbi, token_str: str) -> EdiTokenClaims | None:
    """Check and decode an EDI JSON Web Token (JWT).
    - If the token is valid, an EdiTokenClaims is returned. If invalid, None is returned. If invalid
    due to anything other than having expired, the issue is logged as an error.
    """
    try:
        claims_dict = jwt.decode(token_str, PUBLIC_KEY_STR, algorithms=[Config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError as e:
        log.error(f'Invalid token: {e}')
        return None
    if claims_dict.get('iss') != Config.JWT_ISSUER:
        log.error(f'Invalid issuer in token: {claims_dict.get("iss")}')
        return None
    if claims_dict.get('hd') != Config.JWT_HOSTED_DOMAIN:
        log.error(f'Invalid hosted domain in token: {claims_dict.get("hd")}')
        return None
    # Check if the profile still exists in the database. Tokens can only be created for profiles
    # that exist in the database, but it's possible that the profile was deleted after the token was
    # created, in which case the token is invalid even if otherwise valid. Note: If a unit test
    # fails here, it may be because a bug in session management causes the tests to see a different
    # session than the rest of the app.
    try:
        await dbi.get_profile(claims_dict.get('sub'))
    except sqlalchemy.exc.NoResultFound:
        log.error(f'Profile not found for EDI-ID: {claims_dict.get("sub")}')
        return None
    # Convert principals to set for dataclass
    claims_dict['principals'] = set(claims_dict.get('principals', []))
    return EdiTokenClaims(**claims_dict)


async def is_valid(dbi, token_str: str | None) -> bool:
    if not token_str:
        return False
    return await decode(dbi, token_str) is not None


def claims_pformat(claims: EdiTokenClaims) -> str:
    claims_dict = claims.__dict__.copy()
    for k in ['iat', 'nbf', 'exp']:
        ts = claims_dict.get(k)
        if ts is not None:
            claims_dict[k] = f'{ts} ({datetime.datetime.fromtimestamp(ts)})'
    return pprint.pformat(claims_dict, indent=2, sort_dicts=False)
