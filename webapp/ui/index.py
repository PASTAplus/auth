import daiquiri
import fastapi

import util

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


@router.get('/')
async def index(
    # request: starlette.requests.Request,
    # udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    # token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    return util.redirect_internal('/ui/profile')
