import daiquiri
import fastapi
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()
templates = starlette.templating.Jinja2Templates(Config.TEMPLATES_PATH)


@router.get('/')
async def index(
    # request: starlette.requests.Request,
    # udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    # token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    return starlette.responses.RedirectResponse(
        '/ui/profile',
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )
