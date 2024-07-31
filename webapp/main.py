import daiquiri.formatter
import fastapi
import fastapi.staticfiles
import starlette.requests
import starlette.responses

import webapp.api.refresh_token
import webapp.api.ping
import webapp.api.profile
import webapp.idp.github
import webapp.idp.google
import webapp.idp.ldap
import webapp.idp.microsoft
import webapp.idp.orcid
import webapp.ui.index
import webapp.ui.privacy_policy
from webapp.config import Config

daiquiri.setup(
    level=Config.LOG_LEVEL,
    outputs=[
        # daiquiri.output.Journal(),
        daiquiri.output.Stream(),
        daiquiri.output.RotatingFile(
            filename=Config.HERE_PATH / 'auth.log',
            max_size_bytes=10 * 1024 ** 2,
            backup_count=5,
        ),
    ]
)

log = daiquiri.getLogger(__name__)

log.info("Application starting...")

app = fastapi.FastAPI()

# Set up serving of static files
app.mount(
    '/static',
    fastapi.staticfiles.StaticFiles(directory=Config.HERE_PATH / 'static'),
    name='static',
)


# Set up favicon and manifest routes, served from the root
def create_icon_route(app, icon_path: str):
    @app.get(icon_path)
    async def serve_icon():
        try:
            return starlette.responses.FileResponse(f'webapp/static/favicon{icon_path}')
        except FileNotFoundError:
            raise fastapi.HTTPException(status_code=404, detail='File not found')


for icon_path in [
    '/favicon.ico',
    '/edi-32x32.png',
    '/edi-180x180.png',
    '/edi-192x192.png',
    '/edi-512x512.png',
    '/site.webmanifest',
]:
    create_icon_route(app, icon_path)

# @app.middleware('http')
# async def create_db_session(request: starlette.requests.Request, call_next):
#     request.state.session = session_maker_fn()
#     response = await call_next(request)
#     request.state.session.close()
#     return response


app.include_router(webapp.api.refresh_token.router)
app.include_router(webapp.api.ping.router)
app.include_router(webapp.api.profile.router)
app.include_router(webapp.idp.github.router)
app.include_router(webapp.idp.google.router)
app.include_router(webapp.idp.ldap.router)
app.include_router(webapp.idp.microsoft.router)
app.include_router(webapp.idp.orcid.router)
app.include_router(webapp.ui.index.router)
app.include_router(webapp.ui.privacy_policy.router)
