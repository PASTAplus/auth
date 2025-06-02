import contextlib
import typing

import fastapi
import starlette.requests

import db.iface
import db.profile
import db.user
import util.pasta_jwt

# Create class refs here to use as type hints
Profile = db.profile.Profile
UserDb = db.user.UserDb
PastaJwt = util.pasta_jwt.PastaJwt

#
# Async context managers
#


@contextlib.asynccontextmanager
async def get_session():
    async with db.iface.AsyncSessionFactory() as session:
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
async def get_udb() -> typing.AsyncGenerator[UserDb, typing.Any]:
    async with get_session() as session:
        yield db.user.UserDb(session)


#
# Dependency injections (based on the context managers above)
#


async def udb() -> typing.AsyncGenerator[UserDb, typing.Any]:
    """Get a UserDb instance."""
    async with get_udb() as udb:
        yield udb


async def token(
    request: starlette.requests.Request,
    udb_: UserDb = fastapi.Depends(udb),
):
    """Get token from the request cookie.
    :returns: PASTA token if pasta_token cookie present in Request
    :rtype: PastaJwt
    """
    token_str = request.cookies.get('pasta_token')
    token_obj = await util.pasta_jwt.PastaJwt.decode(udb_, token_str) if token_str else None
    yield token_obj


async def token_profile_row(
    udb_: UserDb = fastapi.Depends(udb),
    token_: PastaJwt | None = fastapi.Depends(token),
):
    """Get the profile row associated with the token.
    :returns: The profile row associated with the token, or None if the token is missing or invalid.
    :rtype: Profile | None
    """
    if token_ is not None:
        return await udb_.get_profile(token_.edi_id)
    return None
