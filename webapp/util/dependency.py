import fastapi
import sqlalchemy.orm
import starlette.requests

import db.iface
import db.profile
import db.user
import util.pasta_jwt

# Create class refs here to use as type hints
Profile = db.profile.Profile
UserDb = db.user.UserDb
PastaJwt = util.pasta_jwt.PastaJwt


async def udb(session: sqlalchemy.orm.Session = fastapi.Depends(db.iface.get_session)):
    try:
        yield db.user.UserDb(session)
    finally:
        session.close()


async def token(
    request: starlette.requests.Request,
):
    """Get token from the request cookie."""
    token_str = request.cookies.get('pasta_token')
    token_obj = util.pasta_jwt.PastaJwt.decode(token_str) if token_str else None
    yield token_obj


async def token_profile_row(
    udb_: UserDb = fastapi.Depends(udb),
    token_: PastaJwt | None = fastapi.Depends(token),
):
    """Get the profile row associated with the token. Return None if the token is missing or
    invalid.

    :returns: The profile row associated with the token, or None if the token is missing or invalid.
    :rtype: Profile | None
    """
    if token_ is not None:
        return await udb_.get_profile(token_.pasta_id)
