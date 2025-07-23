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


_session_factory = None


def set_session_factory(session_factory):
    """Set the session factory for dependency injection."""
    global _session_factory
    _session_factory = session_factory


#
# Async context managers
#


@contextlib.asynccontextmanager
async def get_session():
    async with _session_factory() as session:
        async with session.begin():
            try:
                yield session
            except Exception:
                # logging.exception('Exception')
                await session.rollback()
                raise
            else:
                # TODO: Check if the DB engine autocommit setting is a better fit here
                await session.commit()
            finally:
                await session.close()


@contextlib.asynccontextmanager
async def get_dbi() -> typing.AsyncGenerator[DbInterface, typing.Any]:
    async with get_session() as session:
        yield db.db_interface.DbInterface(session)


#
# Dependency injections (based on the context managers above)
#


async def session() -> typing.AsyncGenerator[sqlalchemy.ext.asyncio.AsyncSession, typing.Any]:
    """Get a SQLAlchemy AsyncSession instance."""
    async with get_session() as session:
        yield session


async def dbi() -> typing.AsyncGenerator[DbInterface, typing.Any]:
    """Get a DbInterface instance."""
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
