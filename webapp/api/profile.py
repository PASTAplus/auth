import daiquiri
import fastapi
import starlette.responses
import webapp.user_db

import webapp.old_token
import webapp.util

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()


@router.get('/v1/profile/list')
async def profile_list(
    udb: webapp.user_db.UserDb = fastapi.Depends(webapp.user_db.udb),
):
    """Get a list of all profiles."""
    profile_list = []
    for profile_row in udb.get_all_profiles():
        profile_list.append(profile_row.as_dict())
    # webapp.util.pp(profile_list)
    return starlette.responses.Response(webapp.util.to_pretty_json(profile_list))


# 5. get_profile (IdP, authtoken)
# -> profile/get (token)
@router.get('/v1/profile/get')
async def profile_get(
    token_str: str,
    udb: webapp.user_db.UserDb = fastapi.Depends(webapp.user_db.udb),
):
    """Get a profile."""
    token = webapp.old_token.OldToken()
    token.from_auth_token(token_str)
    profile_row = udb.get_profile(token.uid)
    return starlette.responses.Response(
        webapp.util.to_pretty_json(profile_row.as_dict())
    )


# 1. map_identity (IdP_A, authtoken_A, IdP_B, authtoken_B)
# -> profile/map (token_src, token_dst)
@router.post('/v1/profile/map')
async def profile_map(
    token_src_str: str,
    token_dst_str: str,
    udb: webapp.user_db.UserDb = fastapi.Depends(webapp.user_db.udb),
):
    """Map profile from profile source to profile destination.

    All identities from profile_src are moved to profile_dst. profile_src is then
    deleted.
    """
    token_src = webapp.old_token.OldToken()
    token_src.from_auth_token(token_src_str)
    token_dst = webapp.old_token.OldToken()
    token_dst.from_auth_token(token_dst_str)
    udb.map_profile(token_src.uid, token_dst.uid)


# 6. drop_profile (profile_id, authtoken)
# -> profile/disable (token)
@router.post('/v1/profile/disable')
async def profile_disable(
    token_str: str,
    udb: webapp.user_db.UserDb = fastapi.Depends(webapp.user_db.udb),
):
    """Disable a profile.

    Disabling a profile removes all identities associated with the profile, making it
    impossible to sign in to the profile.
    """
    token = webapp.old_token.OldToken()
    token.from_auth_token(token_str)
    udb.disable_profile(token.uid)


# 3. drop_identity (token, IdP)
# -> identity/drop (token, IdP)
@router.post('/v1/identity/drop')
async def identity_drop(
    token_str: str,
    idp_name: str,
    uid: str,
    udb: webapp.user_db.UserDb = fastapi.Depends(webapp.user_db.udb),
):
    """Drop an identity from a profile.

    Dropping an identity removes the identity from the profile, making it impossible to
    sign in to the profile with the identity.

    If the identity is used again, it will be mapped to a new profile. The user is then free to
    map the new profile to an existing profile if they wish.
    """
    token = webapp.old_token.OldToken()
    token.from_auth_token(token_str)
    udb.drop_identity(token.uid, idp_name, uid)


# 4. list_identities (profile_id, authtoken)
# -> identity/list (token)
@router.get('/v1/identity/list')
async def identity_list(
    token_str: str,
    udb: webapp.user_db.UserDb = fastapi.Depends(webapp.user_db.udb),
):
    """List all identities associated with a profile."""
    token = webapp.old_token.OldToken()
    token.from_auth_token(token_str)
    identity_list = []
    for identity_row in udb.get_identity_list(token.uid):
        identity_list.append(identity_row.as_dict())
    return starlette.responses.Response(webapp.util.to_pretty_json(identity_list))
