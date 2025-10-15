import logging
import pathlib
import re
import time

import daiquiri.formatter
import fastapi
import fastapi.staticfiles
import starlette.middleware.base
import starlette.requests
import starlette.responses
import starlette.status

import api.v1.eml
import api.v1.group
import api.v1.ping
import api.v1.profile
import api.v1.resource
import api.v1.rule
import api.v1.search
import api.v1.token
import idp.github
import idp.google
import idp.ldap
import idp.microsoft
import idp.orcid
import ui.avatar
import ui.dev
import ui.group
import ui.help
import ui.identity
import ui.index
import ui.membership
import ui.permission
import ui.privacy_policy
import ui.profile
import ui.signin
import ui.token
import util.avatar
import util.dependency
import util.edi_token
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


# Create routes for serving specific static files
def create_route(url_path: str, file_path: pathlib.Path):
    """Create a route to serve a specific static file.
    If the file is not found, return a 404 error.
    """
    assert file_path.exists(), f'File does not exist: {file_path}'
    log.debug(f'Creating route for {url_path} -> {file_path}')

    # As with all routes, the root path is prepended automatically.
    @app.get(url_path)
    async def serve_file():
        try:
            return starlette.responses.FileResponse(file_path)
        except FileNotFoundError:
            raise fastapi.HTTPException(
                status_code=starlette.status.HTTP_404_NOT_FOUND, detail='File not found'
            )


create_route('/favicon.svg', Config.STATIC_PATH / 'site/favicon.svg')
create_route('/manifest.json', Config.STATIC_PATH / 'site/manifest.json')


# Middleware

# Note: Middleware is executed in reverse order of addition.


class RedirectToSigninMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    """
    Middleware to redirect unauthenticated users to the sign-in page.
    - If a request is made to a '/ui' path without a valid token, the user is redirected to
    '/signout', which removes the invalid (usually expired) cookie and which then redirects to
    '/ui/signin'.
    - For any other request without a valid token, a 401 Unauthorized response is returned.
    """

    async def dispatch(self, request: starlette.requests.Request, call_next):
        if re.match(fr'{util.url.url("/ui")}(?!/(?:signin(?!/link)|help|api/))', request.url.path):
            if request.state.claims is None:
                # log.debug('Redirecting to /ui/signin: UI page requested without valid token')
                return util.redirect.internal('/signout', info='expired')

        return await call_next(request)


app.add_middleware(RedirectToSigninMiddleware)


class TokenProfileMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    """Middleware to decode the EDI token from the request cookie.
    - If the token is missing or invalid, the token claims is set to None.
    - If the token is older than the refresh delta, but still valid, it is refreshed by adding a new
    token cookie to the response.
    - The token claims is stored in the request state for use by downstream handlers.
    """

    async def dispatch(self, request: starlette.requests.Request, call_next):
        claims_obj = None  # type: util.edi_token.EdiTokenClaims | None

        token_str = request.cookies.get('edi-token')
        if token_str is not None:
            # Note: It's important to not run this code for the unit tests, as it creates a separate
            # session in which the test profiles don't exist, which causes the token to be invalid.
            async with util.dependency.get_dbi() as dbi:
                claims_obj = await util.edi_token.decode(dbi, token_str)
                # A DB row is only valid within the session it was created in, so we cannot store a
                # profile_row here for use in downstream handlers.

        request.state.claims = claims_obj
        response = await call_next(request)

        if (
            # token is still valid
            claims_obj is not None
            # but older than the refresh delta
            and time.time() - claims_obj.iat > Config.JWT_REFRESH_DELTA.total_seconds()
            # and we're not currently signing out
            and not re.match(str(util.url.url('/ui/signout')), request.url.path)
        ):
            async with util.dependency.get_dbi() as dbi:
                profile_row = await dbi.get_profile(claims_obj.edi_id)
                new_token = await util.edi_token.create(dbi, profile_row)
            response.set_cookie('edi-token', new_token)

        return response


app.add_middleware(TokenProfileMiddleware)


class RootPathMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    """Middleware to set the root path for the application.
    - This middleware ensures that the application routes are agnostic of the root path it is being
    served from. It sets the root_path in the ASGI request scope.
    - In addition, it redirects requests that do not start with the root path to the root path.
    """

    async def dispatch(self, request: starlette.requests.Request, call_next):
        if not request.url.path.startswith(Config.ROOT_PATH):
            return util.redirect.internal(request.url.path)
        request.scope['root_path'] = Config.ROOT_PATH
        return await call_next(request)


app.add_middleware(RootPathMiddleware)


# Include all routers
app.include_router(api.v1.eml.router)
app.include_router(api.v1.group.router)
app.include_router(api.v1.ping.router)
app.include_router(api.v1.profile.router)
app.include_router(api.v1.resource.router)
app.include_router(api.v1.rule.router)
app.include_router(api.v1.search.router)
app.include_router(api.v1.token.router)
app.include_router(idp.github.router)
app.include_router(idp.google.router)
app.include_router(idp.ldap.router)
app.include_router(idp.microsoft.router)
app.include_router(idp.orcid.router)
app.include_router(ui.avatar.router)
app.include_router(ui.dev.router)
app.include_router(ui.group.router)
app.include_router(ui.help.router)
app.include_router(ui.identity.router)
app.include_router(ui.index.router)
app.include_router(ui.membership.router)
app.include_router(ui.permission.router)
app.include_router(ui.privacy_policy.router)
app.include_router(ui.profile.router)
app.include_router(ui.signin.router)
app.include_router(ui.token.router)
