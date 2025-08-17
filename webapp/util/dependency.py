import daiquiri
import contextlib
import typing

import fastapi
import sqlalchemy.ext.asyncio
import starlette.requests

import db.db_interface
import db.models.profile
import db.session
import util.pasta_jwt

# Create class refs here to use as type hints
Profile = db.models.profile.Profile
DbInterface = db.db_interface.DbInterface
PastaJwt = util.pasta_jwt.PastaJwt

log = daiquiri.getLogger(__name__)

#
# Async context managers
#


@contextlib.asynccontextmanager
async def get_session():
    async with db.session.get_session_factory()() as session:
        # log.debug('Created a new SQLAlchemy AsyncSession')
        # This context manager handles the session lifecycle, including committing or rolling back
        # transactions and closing the session.
        async with session.begin():
            yield session


@contextlib.asynccontextmanager
async def get_dbi() -> typing.AsyncGenerator[DbInterface, typing.Any]:
    """Get a DbInterface instance.
    This context manager creates a new DbInterface instance using an SQLAlchemy AsyncSession. Note
    that each new DbInterface instance receives a new session, so for the unit tests, any of the
    main application code that uses get_dbi() will not see the test objects.
    """
    async with get_session() as session:
        yield db.db_interface.DbInterface(session)


#
# Dependency injections (based on the context managers above)
#


async def session() -> typing.AsyncGenerator[sqlalchemy.ext.asyncio.AsyncSession, typing.Any]:
    """Get an SQLAlchemy AsyncSession instance."""
    async with get_session() as session:
        yield session


async def dbi() -> typing.AsyncGenerator[DbInterface, typing.Any]:
    """Get a DbInterface instance.
    This adapts get_dbi(), which is an async context manager, to be used as a FastAPI dependency,
    which needs a synchronous function that yields a value.
    """
    async with get_dbi() as dbi:
        yield dbi


async def token(
    request: starlette.requests.Request,
    dbi_: DbInterface = fastapi.Depends(dbi),
):
    """Get token from the request cookie.
    :returns: EDI token if edi-token cookie present in Request
    :rtype: PastaJwt
    """
    token_str = request.cookies.get('edi-token')
    token_obj = await util.pasta_jwt.PastaJwt.decode(dbi_, token_str) if token_str else None
    yield token_obj


async def token_profile_row(
    dbi_: DbInterface = fastapi.Depends(dbi),
    token_: PastaJwt | None = fastapi.Depends(token),
):
    """Get the profile row associated with the token.
    :returns: The profile row associated with the token, or None if the token is missing or invalid.
    :rtype: Profile | None
    """
    if token_ is not None:
        return await dbi_.get_profile(token_.edi_id)
    return None
