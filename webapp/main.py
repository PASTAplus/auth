import contextlib
import pathlib
import logging

import daiquiri.formatter
import fastapi
import fastapi.staticfiles
import starlette.middleware.base
import starlette.requests
import starlette.responses
import starlette.status

import api.ping
import api.refresh_token
import idp.github
import idp.google
import idp.ldap
import idp.microsoft
import idp.orcid
import ui.avatar
import ui.dev
import ui.group
import ui.identity
import ui.index
import ui.membership
import ui.permission
import ui.privacy_policy
import ui.profile
import ui.signin
import util.avatar
import util.pasta_jwt
import util.redirect
import util.search_cache
import util.url
import util.dependency

from fastapi_app import app
from config import Config

daiquiri.setup(
    level=Config.LOG_LEVEL,
    outputs=[
        daiquiri.output.File(
            Config.LOG_PATH,
            formatter=daiquiri.formatter.ColorExtrasFormatter(
                fmt=Config.LOG_FORMAT,
                datefmt=Config.LOG_DATE_FORMAT,
            ),
            level=Config.LOG_LEVEL,
        ),
        daiquiri.output.Stream(
            formatter=daiquiri.formatter.ColorExtrasFormatter(
                fmt=Config.LOG_FORMAT,
                datefmt=Config.LOG_DATE_FORMAT,
            ),
            level=Config.LOG_LEVEL,
        ),
    ],
)

# Mute noisy debug output from dependencies
daiquiri.getLogger("filelock").setLevel(logging.WARNING)
# daiquiri.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

log = daiquiri.getLogger(__name__)


# Set up serving of static files
app.mount(
    '/static',
    fastapi.staticfiles.StaticFiles(directory=Config.STATIC_PATH),
    name='static',
)

# Custom StaticFiles class to set MIME type
class AvatarFiles(fastapi.staticfiles.StaticFiles):
    """Custom StaticFiles class to set the mimetype for SVG files."""

    async def get_response(self, path, scope):
        full_path, stat_result = self.lookup_path(path)
        if stat_result is None:
            raise fastapi.HTTPException(status_code=404, detail="File not found")
        return starlette.responses.FileResponse(
            full_path,
            stat_result=stat_result,
            media_type='image/svg+xml' if await self.is_svg(full_path) else 'image/*',
        )

    async def is_svg(self, path):
        with open(path, 'rb') as f:
            return b'<?xml' in f.read(16).lower()


# Set up serving of avatars
app.mount(
    Config.AVATARS_URL,
    AvatarFiles(directory=Config.AVATARS_PATH),
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


#
# Middleware
#


class RootPathMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    async def dispatch(self, request: starlette.requests.Request, call_next):
        if not request.url.path.startswith(Config.ROOT_PATH):
            return util.redirect.internal(request.url.path)
        # Setting the root_path here has the same effect as setting it in the reverse proxy (e.g.,
        # nginx). We just set it here so that we can avoid special nginx configuration. The
        # root_path setting is part of the ASGI spec, and is used by FastAPI to properly route
        # requests. With this, we can keep routes agnostic of the root path the app is being served
        # from.
        request.scope['root_path'] = Config.ROOT_PATH
        return await call_next(request)


class RedirectToSigninMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    async def dispatch(self, request: starlette.requests.Request, call_next):
        # If the request is for a /ui path, redirect to signin if the token is invalid
        async with util.dependency.get_udb() as udb:
            if (
                request.url.path.startswith(str(util.url.url('/ui')))
                and not request.url.path.startswith(str(util.url.url('/ui/signin')))
                and not await util.pasta_jwt.PastaJwt.is_valid(udb, request.cookies.get('pasta_token'))
            ):
                log.debug('Redirecting to /ui/signin: UI page requested without valid token')
                return util.redirect.internal('/signout')
        return await call_next(request)


# class RouterLoggingMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
#     async def dispatch(self, request: starlette.requests.Request, call_next):
#         log.info(f'>>> {request.method} {request.url}')
#         response = await call_next(request)
#         log.info(f'<<< {response.status_code}')
#         return response


# class SuppressGetLoggingMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
#     async def dispatch(self, request: starlette.requests.Request, call_next):
#         if request.method == "GET":
#             # Suppress logging for GET requests
#             return await call_next(request)
#         # Log other requests
#         log.info(f"{request.method} {request.url}")
#         return await call_next(request)


# noinspection PyTypeChecker
app.add_middleware(RootPathMiddleware)
# noinspection PyTypeChecker
# app.add_middleware(RouterLoggingMiddleware)
# noinspection PyTypeChecker
app.add_middleware(RedirectToSigninMiddleware)
# noinspection PyTypeChecker
# app.add_middleware(SuppressGetLoggingMiddleware)

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
app.include_router(ui.permission.router)
app.include_router(ui.privacy_policy.router)
app.include_router(ui.profile.router)
app.include_router(ui.signin.router)
