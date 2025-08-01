import contextlib

import daiquiri
import fastapi

import db.models.base
import db.models.base
import db.session
import db.session
import util.dependency
import util.dependency
import util.search_cache
import util.search_cache

log = daiquiri.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(
    _app: fastapi.FastAPI,
):
    log.info('Application starting...')

    async with util.dependency.get_dbi() as dbi:
        # Create missing tables
        await dbi.session.run_sync(
            lambda sync_session: db.models.base.Base.metadata.create_all(bind=sync_session.bind)
        )
        # Initialize the profile and group search cache
        await util.search_cache.init_cache(dbi)
        # # Update known package scopes
        # await dbi.init_search_package_scopes()
        # # Update known resource types
        # await dbi.init_search_resource_types()
        # # Update the roots of the resource tree
        # await dbi.init_search_root_resources()

    # Run the app
    yield

    log.info('Application stopping...')

    await db.session.async_engine.dispose()


app = fastapi.FastAPI(lifespan=lifespan)
