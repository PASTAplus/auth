import daiquiri
import fastapi
import starlette.requests

import db.iface
import util

log = daiquiri.getLogger(__name__)


class NewToken:
    def __init__(
        self,
        urid: str | None = None,
        groups: list | None = None,
    ):
        self._urid = urid
        self._groups = groups

    @property
    def urid(self) -> str:
        return self._urid

    @urid.setter
    def urid(self, urid: str):
        self._urid = urid

    @property
    def groups(self) -> list:
        return self._groups or []

    @groups.setter
    def groups(self, groups: list | None):
        self._groups = groups

    def __str__(self) -> str:
        return f'urid={self.urid}, groups={"|".join(self.groups)}'

    async def as_json(self) -> str:
        return util.to_pretty_json(self.as_dict())

    def as_dict(self) -> dict:
        return {
            'urid': self.urid,
            'groups': self.groups,
        }

    def from_dict(self, token_dict: dict):
        self.urid = token_dict.get('urid')
        self.groups = token_dict.get('groups')
        return self

    def from_json(self, token_json: str):
        return self.from_dict(util.from_json(token_json))


def token(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
):
    token_json = request.cookies.get('token')
    if token_json is None:
        # Trigger redirect to signin page
        request.state.redirect_to_signin = True
        yield None
    else:
        yield NewToken().from_json(token_json)
