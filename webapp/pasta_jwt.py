import datetime

import daiquiri
import jwt
import starlette.requests

import util
from config import Config

log = daiquiri.getLogger(__name__)


class PastaJwt:
    """Encode, decode and hold the claims of a JWT.

    A JSON Web Token (JWT) is JSON string in a specific format. This class encodes,
    decodes and represents the claims of a PASTA JWT, but is not itself a JWT.
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
                # 'aud': Config.JWT_AUDIENCE,
                'hd': Config.JWT_HOSTED_DOMAIN,
                'groups': set(claims_dict.get('groups', [])),
                'iat': int(now_dt.timestamp()),
                'nbf': int(now_dt.timestamp()),
                'exp': int((now_dt + Config.JWT_EXPIRATION_DELTA).timestamp()),
            }
        )

    def __str__(self) -> str:
        return f'{self.__class__.__name__}' f'(sub={self._claims_dict.get("sub")})'

    @property
    def urid(self) -> str:
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
        return util.pformat(claims_dict)

    def _add_dt(self, claims_dict: dict, key: str):
        """Add a datetime object to the claims."""
        ts = claims_dict.get(key)
        if ts is not None:
            claims_dict[key] = f'{ts} ({datetime.datetime.fromtimestamp(ts)})'

    def encode(self) -> str:
        """Encode the PastaJwt to a string for sending to client."""
        claims_dict = self._claims_dict.copy()
        claims_dict['groups'] = list(claims_dict['groups'])
        log.info(f'Encoding token: {claims_dict}')
        return jwt.encode(
            claims_dict, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM
        )

    @classmethod
    def decode(cls, token_str: str):
        """Decode a token and return a PastaJwt instance.

        If the token is invalid, return None.
        """
        try:
            claims_dict = jwt.decode(
                token_str, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM]
            )
            return cls(claims_dict)
        except jwt.ExpiredSignatureError:
            bad_claims_dict = jwt.decode(
                token_str,
                Config.JWT_SECRET_KEY,
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
            jwt.decode(
                token_str, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM]
            )
            return True
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
            log.error(f'Invalid token: {e}: {token_str}')
            return False


async def token(
    request: starlette.requests.Request,
):
    """Get token from the request cookie."""
    token_str = request.cookies.get('pasta_token')
    token_obj = PastaJwt.decode(token_str) if token_str else None
    yield token_obj


def make_jwt(udb, identity_row, is_vetted):
    """Create a JWT for the given profile."""
    profile_row = identity_row.profile
    groups_set = udb.get_group_membership_grid_set(profile_row)
    groups_set.add(Config.AUTHENTICATED)
    if is_vetted:
        groups_set.add('vetted')  # Can't use Config.VETTED here
    pasta_jwt = PastaJwt(
        {
            'sub': profile_row.urid,
            'groups': groups_set,
            'cn': profile_row.full_name,
            'gn': profile_row.given_name,
            'sn': profile_row.family_name,
            'email': profile_row.email,
            # We don't have an email verification procedure yet
            'email_verified': False,
            'email_notifications': profile_row.email_notifications,
            # Claims for account linking and client transitions
            'idp_name': identity_row.idp_name,
            'uid': identity_row.uid,
        }
    )
    log.info('Created PASTA JWT:')
    log.info(pasta_jwt.claims_pp)
    return pasta_jwt.encode()


# def refresh_token(
#     token: PastaJwt = fastapi.Depends(token),
# ):
#     if token is None:
#         return None
#     return token.encode()
