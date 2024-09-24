import daiquiri
import fastapi
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.iface
import new_token
from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()
templates = starlette.templating.Jinja2Templates(Config.TEMPLATES_PATH)


@router.get('/')
async def index(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: new_token.NewToken | None = fastapi.Depends(new_token.token),
):
    """The index page."""
    profile_list = udb.get_all_profiles()
    return templates.TemplateResponse(
        'index.html',
        {
            # Base
            'token': token,
            #
            'request': request,
            'profile_list': profile_list,
        },
    )


@router.get('/dev')
async def dev(request: starlette.requests.Request):
    response = starlette.responses.RedirectResponse(
        Config.SERVICE_BASE_URL + '/profile',
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )
    token = new_token.NewToken(urid='PASTA-ea1877bbdf1e49cea9761c09923fc738')
    response.set_cookie(key='token', value=await token.as_json())
    return response
