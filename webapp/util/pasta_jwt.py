import datetime
import pprint

import daiquiri
import jwt

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
                'pastaGroups': set(claims_dict.get('pastaGroups', [])),
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
        """Return a pretty-printed version of the claims."""
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
        claims_dict['pastaGroups'] = list(claims_dict['pastaGroups'])
        log.info(f'Encoding token: {claims_dict}')
        return jwt.encode(claims_dict, PRIVATE_KEY_STR, algorithm=Config.JWT_ALGORITHM)

    @classmethod
    def decode(cls, token_str: str):
        """Decode a token and return a PastaJwt instance.

        If the token is invalid, return None.
        """
        try:
            claims_dict = jwt.decode(token_str, PUBLIC_KEY_STR, algorithms=[Config.JWT_ALGORITHM])
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
    def is_valid(cls, token_str: str | None):
        """Check if a token is valid."""
        if token_str is None:
            return False
        try:
            jwt.decode(token_str, PUBLIC_KEY_STR, algorithms=[Config.JWT_ALGORITHM])
            return True
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
            log.error(f'Invalid token: {e}: {token_str}')
            return False


async def make_jwt(udb, identity_row, is_vetted):
    """Create a JWT for the given profile."""
    profile_row = identity_row.profile
    pasta_jwt = PastaJwt(
        {
            'sub': profile_row.edi_id,
            'cn': profile_row.full_name,
            'gn': profile_row.given_name,
            'email': profile_row.email,
            'sn': profile_row.family_name,
            'pastaGroups': await udb.get_group_membership_pasta_id_set(profile_row),
            'pastaIsEmailEnabled': profile_row.email_notifications,
            # We don't have an email verification procedure yet
            'pastaIsEmailVerified': False,
            'pastaIsVetted': is_vetted,
            # As we currently do not issue JWT tokens to public users, we can assume
            # that the user is authenticated if they have a valid JWT.
            'pastaIsAuthenticated': True,
            'pastaIdentityId': identity_row.id,
        }
    )
    log.info('Created PASTA JWT:')
    log.info(pasta_jwt.claims_pp)
    return pasta_jwt.encode()
