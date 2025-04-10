import base64

import daiquiri
import pendulum

import util.pasta_crypto
from config import Config

log = daiquiri.getLogger(__name__)


class OldToken(object):
    def __init__(self):
        self._token = {
            'uid': '',
            'system': '',
            'ttl': OldToken.new_ttl(),
            'groups': '',
        }

    @staticmethod
    def new_ttl() -> str:
        now = pendulum.now()
        return str(int(now.timestamp() * 1000) + Config.TTL)

    @property
    def groups(self) -> str:
        return self._token['groups']

    @groups.setter
    def groups(self, groups: str):
        self._token['groups'] = groups

    @property
    def system(self) -> str:
        return self._token['system']

    @system.setter
    def system(self, system: str):
        self._token['system'] = system

    @property
    def ttl(self) -> str:
        return self._token['ttl']

    @ttl.setter
    def ttl(self, ttl: str):
        self._token['ttl'] = ttl

    @property
    def uid(self) -> str:
        return self._token['uid']

    @uid.setter
    def uid(self, uid: str):
        self._token['uid'] = uid

    def to_b64(self):
        return base64.b64encode(self.to_string().encode('utf-8'))

    def from_b64(self, t_b64: str):
        t = (base64.b64decode(t_b64)).decode('utf-8')
        self.from_string(t)

    def to_string(self) -> str:
        token = list()
        for t in self._token:
            if self._token[t] != '':
                token.append(self._token[t])
        return '*'.join(token)

    def from_string(self, t: str):
        token = t.split('*')
        self._token['uid'] = token[0]
        self._token['system'] = token[1]
        self._token['ttl'] = token[2]
        self._token['groups'] = '*'.join(token[3:])

    def is_valid_ttl(self) -> bool:
        now = int(pendulum.now().timestamp() * 1000)
        delta = int(self._token['ttl']) - now
        return delta > 1

    def ttl_to_iso(self) -> str:
        dt = pendulum.from_timestamp(int(self._token['ttl']) * 0.001, tz='America/Denver')
        return dt.to_iso8601_string()

    def from_auth_token(self, at: str):
        t_b64 = at.split('-')[0]
        self.from_b64(t_b64)


def make_old_token(uid, groups=''):
    old_token_obj = OldToken()
    old_token_obj.system = Config.SYSTEM
    old_token_obj.uid = uid
    old_token_obj.groups = groups
    private_key = util.pasta_crypto.import_key(Config.PASTA_TOKEN_PRIVATE_KEY_PATH)
    log.debug(f'Creating token: {old_token_obj.to_string()}')
    old_token_str = util.pasta_crypto.create_auth_token(private_key, old_token_obj.to_string())
    return old_token_str
