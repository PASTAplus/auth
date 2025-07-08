import datetime
import pprint

import daiquiri
import jwt

import db.models.identity
from config import Config

log = daiquiri.getLogger(__name__)

PRIVATE_KEY_STR = Config.JWT_PRIVATE_KEY_PATH.read_text()
PUBLIC_KEY_STR = Config.JWT_PUBLIC_KEY_PATH.read_text()


class PastaJwt:
    """Encode, decode and hold the claims of a JWT.

    A JSON Web Token (JWT) is JSON string in a specific format. This class encodes, decodes and
    represents the claims of a PASTA JWT, but is not itself a JWT.
    """

    def __init__(
        self,
        claims_dict: dict,
    ):
        self._claims_dict = claims_dict
        now_dt = datetime.datetime.now(datetime.UTC)
        self._claims_dict.update(
            {
                'iss': Config.JWT_ISSUER,
                'hd': Config.JWT_HOSTED_DOMAIN,
                'iat': int(now_dt.timestamp()),
                'nbf': int(now_dt.timestamp()),
                'exp': int((now_dt + Config.JWT_EXPIRATION_DELTA).timestamp()),
                'principals': set(claims_dict.get('principals', [])),
            }
        )

    def __str__(self) -> str:
        return f'{self.__class__.__name__}' f'(sub={self._claims_dict.get("sub")})'

    @property
    def edi_id(self) -> str:
        return self._claims_dict.get('sub')

    @property
    def claims(self) -> dict:
        return self._claims_dict

    @property
    def claims_pp(self) -> str:
        """Pretty print the claims."""
        claims_dict = self._claims_dict.copy()
        for k in ['iat', 'nbf', 'exp']:
            self._add_dt(claims_dict, k)
        return pprint.pformat(claims_dict, indent=2, sort_dicts=True)

    def _add_dt(self, claims_dict: dict, key: str):
        """Add a datetime object to the claims."""
        ts = claims_dict.get(key)
        if ts is not None:
            claims_dict[key] = f'{ts} ({datetime.datetime.fromtimestamp(ts)})'

    def encode(self) -> str:
        """Encode the PastaJwt to a string for sending to client."""
        claims_dict = self._claims_dict.copy()
        claims_dict['principals'] = list(sorted(claims_dict['principals']))
        log.info(f'Encoding token: {claims_dict}')
        return jwt.encode(claims_dict, PRIVATE_KEY_STR, algorithm=Config.JWT_ALGORITHM)

    @classmethod
    async def decode(cls, dbi, token_str: str):
        """Decode a token and return a PastaJwt instance.

        If the token is invalid, return None.
        """
        try:
            claims_dict = jwt.decode(token_str, PUBLIC_KEY_STR, algorithms=[Config.JWT_ALGORITHM])
            if claims_dict.get('iss') != Config.JWT_ISSUER:
                log.error(f'Invalid issuer in token: {claims_dict.get("iss")}')
                return None
            if claims_dict.get('hd') != Config.JWT_HOSTED_DOMAIN:
                log.error(f'Invalid hosted domain in token: {claims_dict.get("hd")}')
                return None
            profile_row = await dbi.get_profile(claims_dict.get("sub"))
            if profile_row is None:
                log.error(f'Profile not found for EDI-ID: {claims_dict.get("sub")}')
                # # Print all profiles
                # all_profiles = await dbi.get_all_profiles()
                # log.error('#'*100)
                # log.error('Available profiles:')
                # for profile in all_profiles:
                #     log.error(f'  - {profile.edi_id} ({profile.common_name})')
                # else:
                #     log.error('NONE')
                return None
            return cls(claims_dict)
        except jwt.ExpiredSignatureError:
            bad_claims_dict = jwt.decode(
                token_str,
                PUBLIC_KEY_STR,
                algorithms=[Config.JWT_ALGORITHM],
                options={'verify_exp': False, 'verify_signature': False},
            )
            log.warn(f'Token has expired: {bad_claims_dict}')
            return None
        except jwt.InvalidTokenError as e:
            log.error(f'Invalid token: {e}')
            return None

    @classmethod
    async def is_valid(cls, dbi, token_str: str | None):
        """Check if a token is valid."""
        if not token_str:
            return False
        return await cls.decode(dbi, token_str) is not None


async def make_jwt(dbi, identity_row):
    """Create a JWT for the given profile."""
    profile_row = identity_row.profile
    principals_set = await dbi.get_equivalent_principal_edi_id_set(profile_row)
    # Remove the profile's own EDI-ID from the principals set, as it's available in the 'sub' claim.
    principals_set.remove(profile_row.edi_id)
    pasta_jwt = PastaJwt(
        {
            'sub': profile_row.edi_id,
            'cn': profile_row.common_name,
            'email': profile_row.email,
            'principals': principals_set,
            'isEmailEnabled': profile_row.email_notifications,
            # We don't have an email verification procedure yet
            'isEmailVerified': False,
            'identityId': identity_row.id,
            # The remaining fields should be deprecated in the future.
            'idpName': identity_row.idp_name.name.lower(),
            # Legacy behavior for Google was to use the email address as subject
            'idpUid': (
                identity_row.email
                if identity_row.idp_name == db.models.identity.IdpName.GOOGLE
                else identity_row.idp_uid
            ),
            'idpCname': identity_row.common_name,
        }
    )
    log.info('Created PASTA JWT:')
    log.info(pasta_jwt.claims_pp)
    return pasta_jwt.encode()
