import logging
import pathlib

import daiquiri.formatter
import fastapi
import fastapi.staticfiles
import starlette.middleware.base
import starlette.requests
import starlette.responses
import starlette.status
import api.v1.ping
import api.v1.profile
import api.v1.resource
import api.v1.rule
import api.v1.token
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
import ui.token
import ui.token
import util.avatar
import util.dependency
import util.pasta_jwt
import util.redirect
import util.search_cache
import util.url
from config import Config
from fastapi_app import app

# Configure logging using the daiquiri library
daiquiri.setup(
    level=Config.LOG_LEVEL,
    outputs=[
        # Log to a file with a custom formatter
        daiquiri.output.File(
            Config.LOG_PATH,
            formatter=daiquiri.formatter.ColorExtrasFormatter(
                fmt=Config.LOG_FORMAT,
                datefmt=Config.LOG_DATE_FORMAT,
            ),
            level=Config.LOG_LEVEL,
        ),
        # Log to the console with a custom formatter
        daiquiri.output.Stream(
            formatter=daiquiri.formatter.ColorExtrasFormatter(
                fmt=Config.LOG_FORMAT,
                datefmt=Config.LOG_DATE_FORMAT,
            ),
            level=Config.LOG_LEVEL,
        ),
    ],
)

# Suppress noisy debug logs from specific dependencies
daiquiri.getLogger('filelock').setLevel(logging.WARNING)
# daiquiri.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

log = daiquiri.getLogger(__name__)

# Serve static files from the configured static path
app.mount(
    '/static',
    fastapi.staticfiles.StaticFiles(directory=Config.STATIC_PATH),
    name='static',
)

# Custom StaticFiles class to set MIME type for SVG files
class AvatarFiles(fastapi.staticfiles.StaticFiles):
    """Custom StaticFiles class to set the MIME type for SVG files."""

    async def get_response(self, path, scope):
        """Serve a file with the appropriate MIME type.
        If the file is an SVG, set the MIME type to 'image/svg+xml'.
        """
        full_path, stat_result = self.lookup_path(path)
        if stat_result is None:
            raise fastapi.HTTPException(status_code=404, detail='File not found')
        return starlette.responses.FileResponse(
            full_path,
            stat_result=stat_result,
            media_type='image/svg+xml' if await self.is_svg(full_path) else 'image/*',
        )

    async def is_svg(self, path):
        """Check if the file is an SVG by reading its first few bytes."""
        with open(path, 'rb') as f:
            return b'<?xml' in f.read(16).lower()


# Serve avatar files from the configured avatars path
app.mount(
    Config.AVATARS_URL,
    AvatarFiles(directory=Config.AVATARS_PATH),
    name='avatars',
)

# Dynamically create routes for serving specific static files
def create_route(file_path: pathlib.Path):
    """Create a route to serve a specific static file.
    If the file is not found, return a 404 error.
    """

    @app.get(f'/{file_path.name}')
    async def serve_file():
        try:
            return starlette.responses.FileResponse(file_path)
        except FileNotFoundError:
            raise fastapi.HTTPException(
                status_code=starlette.status.HTTP_404_NOT_FOUND, detail='File not found'
            )


# Middleware


class RootPathMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    """Middleware to set the root path for the application.
    This middleware ensures that the application routes are agnostic of the root path
    it is being served from. It sets the root_path in the ASGI request scope.
    In addition, it redirects requests that do not start with the root path to the root path.
    """

    async def dispatch(self, request: starlette.requests.Request, call_next):
        if not request.url.path.startswith(Config.ROOT_PATH):
            return util.redirect.internal(request.url.path)
        request.scope['root_path'] = Config.ROOT_PATH
        return await call_next(request)


class RedirectToSigninMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    """
    Middleware to redirect unauthenticated users to the sign-in page.

    If a request is made to a '/ui' path without a valid token, the user is redirected to
    '/signout', which removes the invalid (usually expired) cookie, and which then redirects to
    '/ui/signin'.

    For any other request without a valid token, a 401 Unauthorized response is returned.
    """

    async def dispatch(self, request: starlette.requests.Request, call_next):
        async with util.dependency.get_dbi() as dbi:
            is_valid_token = await util.pasta_jwt.PastaJwt.is_valid(
                dbi, request.cookies.get('edi-token')
            )

        if (
            not is_valid_token
            and request.url.path.startswith(str(util.url.url('/ui')))
            and not request.url.path.startswith(str(util.url.url('/ui/signin')))
            and not request.url.path.startswith(str(util.url.url('/ui/api/')))
        ):
            log.debug('Redirecting to /ui/signin: UI page requested without valid token')
            return util.redirect.internal('/signout')

        # if not is_valid_token:
        #     return starlette.responses.Response(
        #         'Unauthorized: Authentication token is missing or invalid',
        #         status_code=starlette.status.HTTP_401_UNAUTHORIZED,
        #     )

        return await call_next(request)


# Add middleware to the application
app.add_middleware(RootPathMiddleware)
app.add_middleware(RedirectToSigninMiddleware)

# Include all routers
app.include_router(api.v1.ping.router)
app.include_router(api.v1.profile.router)
app.include_router(api.v1.resource.router)
app.include_router(api.v1.rule.router)
app.include_router(api.v1.token.router)
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
app.include_router(ui.token.router)
