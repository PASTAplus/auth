import contextlib
import pathlib

import daiquiri.formatter
import fastapi
import fastapi.staticfiles
import starlette.middleware.base
import starlette.requests
import starlette.responses
import starlette.status

import api.ping
import api.refresh_token
import fuzz
import idp.github
import idp.google
import idp.ldap
import idp.microsoft
import idp.orcid
import pasta_jwt
import ui.avatar
import ui.dev
import ui.group
import ui.identity
import ui.index
import ui.membership
import ui.privacy_policy
import ui.profile
import ui.signin
import util
from config import Config

daiquiri.setup(
    level=Config.LOG_LEVEL,
    outputs=[
        daiquiri.output.File(Config.LOG_PATH / 'auth.log'),
        'stdout',
    ],
    # formatter=daiquiri.formatter.ColorExtrasFormatter(
    #     # fmt=(Config.LOG_FORMAT),
    #     # datefmt=Config.LOG_DATE_FORMAT,
    # ),
)

log = daiquiri.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(
    _app: fastapi.FastAPI,
):
    log.info('Application starting...')
    await fuzz.init_cache()
    yield
    log.info('Application stopping...')


app = fastapi.FastAPI(lifespan=lifespan)

# Set up serving of static files
app.mount(
    '/static',
    fastapi.staticfiles.StaticFiles(directory=Config.STATIC_PATH),
    name='static',
)

# Set up serving of avatars
app.mount(
    Config.AVATARS_URL,
    fastapi.staticfiles.StaticFiles(directory=Config.AVATARS_PATH),
    name='avatars',
)


# Set up favicon and manifest routes, served from the root
def create_route(file_path: pathlib.Path):
    @app.get(f'/{file_path.name}')
    async def serve_file():
        try:
            return starlette.responses.FileResponse(file_path)
        except FileNotFoundError:
            raise fastapi.HTTPException(
                status_code=starlette.status.HTTP_404_NOT_FOUND, detail='File not found'
            )


for file_path in (Config.STATIC_PATH / 'site').iterdir():
    create_route(file_path)


class RootPathMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    async def dispatch(self, request: starlette.requests.Request, call_next):
        request.scope['root_path'] = Config.ROOT_PATH
        return await call_next(request)


class RedirectToSigninMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    async def dispatch(self, request: starlette.requests.Request, call_next):
        # If the request is for a /ui path, redirect to signin if the token is invalid
        if (
            request.url.path.startswith(str(util.url('/ui')))
            and not request.url.path.startswith(str(util.url('/ui/signin')))
            and not pasta_jwt.PastaJwt.is_valid(request.cookies.get('pasta_token'))
        ):
            log.debug('Redirecting to /ui/signin: UI page requested without valid token')
            return util.redirect_internal('/ui/signin')
        return await call_next(request)


# noinspection PyTypeChecker
app.add_middleware(RootPathMiddleware)
# noinspection PyTypeChecker
app.add_middleware(RedirectToSigninMiddleware)

app.include_router(api.refresh_token.router)
app.include_router(api.ping.router)
# app.include_router(api.user.router)
app.include_router(idp.github.router)
app.include_router(idp.google.router)
app.include_router(idp.ldap.router)
app.include_router(idp.microsoft.router)
app.include_router(idp.orcid.router)
app.include_router(ui.avatar.router)
app.include_router(ui.dev.router)
app.include_router(ui.group.router)
app.include_router(ui.identity.router)
app.include_router(ui.index.router)
app.include_router(ui.membership.router)
app.include_router(ui.privacy_policy.router)
app.include_router(ui.profile.router)
app.include_router(ui.signin.router)
