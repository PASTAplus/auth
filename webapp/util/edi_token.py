"""Encode and decode EDI Tokens.
- EDI Tokens are JSON Web Token (JWTs). A JWT consists of a header, a JSON payload, and a signature.
These are Base64URL encoded and combined into a single string with the parts separated by dots.
- The header specifies the algorithm used to sign the token, and other metadata.
- The payload contains the claims, which are statements about a user profile and metadata about the
token itself.
- The signature ensures that the token was created by EDI and has not been modified.
"""

import dataclasses
import datetime
import pprint

import daiquiri
import jwt
import sqlalchemy.exc

import db.models.profile
from config import Config

log = daiquiri.getLogger(__name__)

PRIVATE_KEY_STR = Config.JWT_PRIVATE_KEY_PATH.read_text()
PUBLIC_KEY_STR = Config.JWT_PUBLIC_KEY_PATH.read_text()


@dataclasses.dataclass
class EdiTokenClaims:
    """Hold the claims of an EDI JWT.
    - We use this instead of the plain dict that represents the JSON in a decoded JWT in order to
    formalize the claims. This also enables convenient access via attributes and helps the IDE with
    autocomplete, syntax checking, etc.
    """

    def __post_init__(self):
        now_dt = datetime.datetime.now(datetime.UTC)
        self.iat = self.iat or int(now_dt.timestamp())
        self.nbf = self.nbf or int(now_dt.timestamp())
        self.exp = self.exp or int((now_dt + Config.JWT_EXPIRATION_DELTA).timestamp())

    sub: str
    cn: str | None = None
    email: str | None = None
    principals: set[str] = dataclasses.field(default_factory=set)
    links: list[dict] = dataclasses.field(default_factory=list)
    isEmailEnabled: bool = False
    isEmailVerified: bool = False
    idpCommonName: str | None = None
    idpName: str | None = None
    idpUid: str | None = None
    iss: str = Config.JWT_ISSUER
    hd: str = Config.JWT_HOSTED_DOMAIN
    iat: int | None = None
    nbf: int | None = None
    exp: int | None = None

    @property
    def edi_id(self):
        return self.sub


async def create(dbi, profile_row) -> str:
    """Create an EDI JSON Web Token (JWT) for a profile."""
    claims_obj = await create_claims(dbi, profile_row)
    return _create(claims_obj)


async def create_by_group(group_row) -> str:
    """Create an EDI JSON Web Token (JWT) for a group."""
    claims_obj = await create_claims_by_group(group_row)
    return _create(claims_obj)


async def create_claims(dbi, profile_row) -> EdiTokenClaims:
    principals_set: set = await dbi.get_equivalent_principal_edi_id_set(profile_row)
    links_list = await dbi.get_link_history_list(profile_row)
    principals_set.discard(profile_row.edi_id)
    return EdiTokenClaims(
        sub=profile_row.edi_id,
        cn=profile_row.common_name,
        email=profile_row.email,
        principals=principals_set,
        links=[
            {
                'ediId': r.edi_id,
                'linkedAt': int(r.link_date.timestamp()),
                'commonName': r.common_name,
                'email': r.email,
                'idpCommonName': r.idp_common_name,
                'idpName': r.idp_name.name.lower(),
                'idpUid': (
                    r.email if r.idp_name == db.models.profile.IdpName.GOOGLE else r.idp_uid
                ),
            }
            for r in links_list
        ],
        isEmailEnabled=profile_row.email_notifications,
        isEmailVerified=False,
        idpCommonName=profile_row.idp_common_name,
        idpName=profile_row.idp_name.name.lower(),
        idpUid=(
            profile_row.email
            if profile_row.idp_name == db.models.profile.IdpName.GOOGLE
            else profile_row.idp_uid
        ),
    )


async def create_claims_by_group(group_row) -> EdiTokenClaims:
    return EdiTokenClaims(
        sub=group_row.edi_id,
        cn=group_row.name,
        # email=None,
        # principals=set(),
        # links=[],
        # isEmailEnabled=False,
        # isEmailVerified=False,
        # idpCommonName=None,
        # idpName=None,
        # idpUid=None,
    )


def create_by_claims(**claims_dict):
    return _create(EdiTokenClaims(**claims_dict))


def _create(claims_obj) -> str:
    claims_dict = claims_obj.__dict__.copy()
    claims_dict['principals'] = list(sorted(claims_dict['principals']))
    log.info(f'Creating EDI token: {claims_dict}')
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
    # Check if the profile or group still exists in the database. Tokens can only be created for
    # profiles or groups that exist in the database, but it's possible that the profile or group was
    # deleted after the token was created, in which case the token is invalid even if otherwise
    # valid. Note: If a unit test fails here, it may be because a bug in session management causes
    # the tests to see a different session than the rest of the app.
    try:
        await dbi.get_profile(claims_dict.get('sub'))
    except sqlalchemy.exc.NoResultFound:
        try:
            await dbi.get_group(claims_dict.get('sub'))
        except sqlalchemy.exc.NoResultFound:
            log.error(f'Profile or group not found for EDI-ID: {claims_dict.get("sub")}')
            return None
    # Convert principals to set for dataclass
    claims_dict['principals'] = set(claims_dict.get('principals', []))
    return EdiTokenClaims(**claims_dict)


async def is_valid(dbi, token_str: str | None) -> bool:
    if not token_str:
        return False
    return await decode(dbi, token_str) is not None


async def claims_pformat(dbi, claims: EdiTokenClaims) -> str:
    claims_dict = await format_claims_for_display(dbi, claims)
    return pprint.pformat(claims_dict, indent=2, width=120, sort_dicts=False)


async def format_claims_for_display(dbi, claims: EdiTokenClaims) -> dict[str, object]:
    """Add context to claims for display.
    - Add common names and group names to EDI-IDs.
    - Add human-readable form of timestamps.
    """
    claims_dict = claims.__dict__.copy()

    principals_list = list(claims_dict['principals'])
    claims_dict['principals'].clear()
    for edi_id in principals_list:
        claims_dict['principals'].add(await _add_title(dbi, edi_id))

    claims_dict['sub'] = await _add_title(dbi, claims_dict["sub"])

    for k in ['iat', 'nbf', 'exp']:
        claims_dict[k] = _add_date(claims_dict[k])

    for link_dict in claims_dict['links']:
        link_dict['ediId'] = await _add_title(dbi, link_dict['ediId'])
        link_dict['linkedAt'] = _add_date(link_dict['linkedAt'])

    return claims_dict


async def _add_title(dbi, edi_id) -> str:
    try:
        profile_row = await dbi.get_profile(edi_id)
        return f'{edi_id} ({profile_row.common_name or "unspecified"}, {profile_row.email or "no email"})'
    except sqlalchemy.exc.NoResultFound:
        try:
            group_row = await dbi.get_group(edi_id)
            return f'{edi_id} ({group_row.name or "unspecified"})'
        except sqlalchemy.exc.NoResultFound:
            return f'{edi_id} (not found)'


def _add_date(ts: int) -> str:
    date_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S UTC')
    return f'{ts} ({date_str})'
