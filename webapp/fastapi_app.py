import contextlib

import daiquiri
import fastapi

import util.dependency
import util.search_cache

log = daiquiri.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(
    _app: fastapi.FastAPI,
    # udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
):
    log.info('Application starting...')

    async with util.dependency.get_udb() as udb:
        # Initialize the profile and group search cache
        await util.search_cache.init_cache(udb)

    # Run the app
    yield

    log.info('Application stopping...')


app = fastapi.FastAPI(lifespan=lifespan)
