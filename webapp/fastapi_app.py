import contextlib

import daiquiri
import fastapi

import db.models.base
import db.session
import util.dependency
import util.search_cache

log = daiquiri.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(
    _app: fastapi.FastAPI,
):
    log.info('Application starting...')

    async with util.dependency.get_dbi() as dbi:
        # Initialize the profile and group search cache
        # Note: Not visible in the unit tests, as get_dbi() creates a new session.
        await util.search_cache.init_cache(dbi)

    try:
        # Run the app
        yield
    finally:
        log.info('Application stopping...')
        await db.session.get_async_engine().dispose()


app = fastapi.FastAPI(lifespan=lifespan)
