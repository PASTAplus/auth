import contextlib

import daiquiri
import fastapi

import util.dependency
import util.search_cache

log = daiquiri.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(
    _app: fastapi.FastAPI,
    # dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
):
    log.info('Application starting...')

    async with util.dependency.get_udb() as dbi:
        # Initialize the profile and group search cache
        await util.search_cache.init_cache(dbi)

    # Run the app
    yield

    log.info('Application stopping...')


app = fastapi.FastAPI(lifespan=lifespan)
