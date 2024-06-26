import daiquiri
import fastapi
import starlette.requests
import starlette.templating
import starlette.requests

from config import Config
import user_db
import ui.forms

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()
templates = starlette.templating.Jinja2Templates(Config.HERE_PATH / 'templates')


@router.get('/')
async def index(
    request: starlette.requests.Request,
    # db: sqlalchemy.orm.Session = Depends(user_db.get_db),
    udb: user_db.UserDb = fastapi.Depends(user_db.udb),
):
    """The index page."""
    profile_list = udb.get_all_profiles()
    return templates.TemplateResponse(
        'index.html',
        {'request': request, 'profile_list': profile_list},
    )


@router.get('/profile')
async def profile(request: starlette.requests.Request):
    return templates.TemplateResponse(
        'profile.html',
        {'request': request},
    )


@router.get('/identity')
async def identity(request: starlette.requests.Request):
    return templates.TemplateResponse(
        'identity.html',
        {'request': request},
    )


@router.get('/test')
async def test(request: starlette.requests.Request):
    return templates.TemplateResponse(
        'accept.html',
        {
            'request': request,
            'form': ui.forms.AcceptForm(),
            "uid": 'test',
            "target": 'test',
            "idp": 'test',
            "idp_token": 'test',
        },
    )
