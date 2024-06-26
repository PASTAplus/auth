import daiquiri
import fastapi
import fastapi.staticfiles

# import sqlalchemy.orm
import starlette.requests
import starlette.responses
import starlette.responses

import api.refresh_token
import api.user
import idp.github
import idp.google
import idp.ldap
import idp.microsoft
import idp.orcid
import ui.index
import ui.privacy_policy
from config import Config

# daiquiri.setup(
#     level=Config.LOG_LEVEL,
#     outputs=(
#         daiquiri.output.File(HERE_PATH / 'test.log'),
#         'stdout',
#     ),
# )
# import user_db

log = daiquiri.getLogger(__name__)

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


app.include_router(api.refresh_token.router)
app.include_router(api.user.router)
app.include_router(idp.github.router)
app.include_router(idp.google.router)
app.include_router(idp.ldap.router)
app.include_router(idp.microsoft.router)
app.include_router(idp.orcid.router)
app.include_router(ui.index.router)
app.include_router(ui.privacy_policy.router)
