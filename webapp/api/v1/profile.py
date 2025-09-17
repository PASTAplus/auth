"""Profile API v1
Docs:./docs/api/profile.md
"""

import fastapi
import sqlalchemy.exc
import starlette.requests
import starlette.responses

import api.utils
import util.dependency
import util.exc
import util.edi_token
import util.url

router = fastapi.APIRouter(prefix='/v1')


@router.post('/profile')
async def post_v1_profile(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """createProfile(): Create a skeleton profile.
    - Only available to users in the Vetted system group.
    """
    api_method = 'createProfile'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that the token is in the Vetted system group
    if not await dbi.is_vetted(token_profile_row):
        return api.utils.get_response_403_forbidden(
            request, api_method, 'Must be in the Vetted system group to create a profile'
        )
    # Check that the request body is valid JSON
    try:
        request_dict = await api.utils.request_body_to_dict(request)
    except ValueError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Invalid JSON in request body: {e}'
        )
    # Check that the request contains the required fields
    try:
        idp_uid = request_dict['idp_uid']
    except KeyError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Missing field in JSON in request body: {e}'
        )
    # Check if the profile already exists
    try:
        profile_row = await dbi.get_profile_by_idp_uid(idp_uid)
        return api.utils.get_response_200_ok(
            request, api_method, 'An existing profile was used', edi_id=profile_row.edi_id
        )
    except sqlalchemy.exc.NoResultFound:
        # See README.md: Strategy for dealing with Google emails historically used as identifiers
        try:
            profile_row = await dbi.get_profile_by_google_email(idp_uid)
        except sqlalchemy.exc.NoResultFound:
            profile_row = await dbi.create_skeleton_profile(idp_uid=idp_uid)
            # Flush here so we can read out the new edi_id
            await dbi.flush()
    return api.utils.get_response_200_ok(
        request, api_method, 'A new profile was created', edi_id=profile_row.edi_id
    )


@router.get('/profile/{edi_id}')
async def get_v1_profile(
    edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """readProfile(): Read an existing profile"""
    api_method = 'readProfile'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    try:
        profile_row = await dbi.get_profile(edi_id)
    except sqlalchemy.exc.NoResultFound:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Profile does not exist', edi_id=edi_id
        )
    # Retrieved successfully. Return whole or partial profile, depending on whether the requester is
    # the owner of the profile.
    result_dict = dict(
        edi_id=edi_id,
        common_name=profile_row.common_name,
        msg='Profile retrieved by non-owner. Only public fields returned.',
    )
    if token_profile_row.edi_id == edi_id:
        result_dict.update(
            dict(
                email=profile_row.email,
                avatar_url=util.url.get_abs_url(profile_row.avatar_url),
                email_notifications=profile_row.email_notifications,
                privacy_policy_accepted=profile_row.privacy_policy_accepted,
                privacy_policy_accepted_date=profile_row.privacy_policy_accepted_date,
                msg='Profile retrieved by owner. Private and public fields returned.',
            )
        )
    return api.utils.get_response_200_ok(request, api_method, **result_dict)


@router.put('/profile/{edi_id}')
async def update_v1_profile(
    edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """updateProfile(): Update an existing profile"""
    api_method = 'updateProfile'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that the request body is valid JSON
    try:
        request_dict = await api.utils.request_body_to_dict(request)
    except ValueError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Invalid JSON in request body: {e}'
        )
    # Check that the request contains the required fields
    updated_fields = {}
    if 'common_name' in request_dict:
        updated_fields['common_name'] = request_dict['common_name']
    if 'email' in request_dict:
        updated_fields['email'] = request_dict['email']
    if not updated_fields:
        return api.utils.get_response_400_bad_request(
            request, api_method, 'Must provide common_name and/or email to update profile'
        )
    # Check that the profile exists
    try:
        profile_row = await dbi.get_profile(edi_id)
    except sqlalchemy.exc.NoResultFound:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Profile does not exist', edi_id=edi_id
        )
    # Check that the requester is the owner of the profile
    if token_profile_row.edi_id != edi_id:
        return api.utils.get_response_403_forbidden(
            request,
            api_method,
            'You do not have permission to update this profile',
            edi_id=edi_id,
        )
    await dbi.update_profile(token_profile_row, **updated_fields)
    return api.utils.get_response_200_ok(
        request, api_method, 'Profile updated successfully', edi_id=edi_id, **updated_fields
    )


@router.delete('/profile/{edi_id}')
async def delete_v1_profile(
    edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """deleteProfile(): Delete an existing profile"""
    api_method = 'deleteProfile'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that the profile exists
    try:
        profile_row = await dbi.get_profile(edi_id)
    except sqlalchemy.exc.NoResultFound:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Profile does not exist', edi_id=edi_id
        )
    # Check that the requester is the owner of the profile
    if token_profile_row.edi_id != edi_id:
        return api.utils.get_response_403_forbidden(
            request, api_method, 'Only the owner can delete this profile', edi_id=edi_id
        )
    # Delete the profile
    await dbi.delete_profile(token_profile_row)
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Profile deleted successfully. '
        'Please sign in and create a new token if you wish to continue using the API',
        edi_id=edi_id,
    )


# @router.get('/v1/profile/list')
# async def profile_list(
#     dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
# ):
#     """Get a list of all profiles."""
#     profile_list = []
#     for profile_row in await dbi.get_all_profiles():
#         profile_list.append(profile_row.as_dict())
#
#     log.error('############################################# Profile list:')
#     util.pretty.pp(profile_list)
#
#     return starlette.responses.Response(util.pretty.to_pretty_json(profile_list))


# # 6. drop_profile (profile_id, authtoken)
# # -> profile/disable (token)
# @router.post('/v1/profile/disable')
# async def profile_disable(
#     token_str: str,
#     dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
# ):
#     """Disable a profile.
#
#     Disabling a profile removes all identities associated with the profile, making it
#     impossible to sign in to the profile.
#     """
#     token = util.old_token.OldToken()
#     token.from_auth_token(token_str)
#     await dbi.disable_profile(token.uid)


# # 3. drop_identity (token, IdP)
# # -> identity/drop (token, IdP)
# @router.post('/v1/identity/drop')
# async def identity_drop(
#     token_str: str,
#     idp_name: db.models.profile.IdpName,
#     idp_uid: str,
#     dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
# ):
#     """Drop an identity from a profile.
#
#     Dropping an identity removes the identity from the profile, making it impossible to sign in to
#     the profile with the identity.
#
#     If the identity is used again, it will be mapped to a new profile. The user is then free to map
#     the new profile to an existing profile if they wish.
#     """
#     token = util.old_token.OldToken()
#     token.from_auth_token(token_str)
#     await dbi.drop_identity(token.uid, idp_name, idp_uid)


# # 4. list_identities (profile_id, authtoken)
# # -> identity/list (token)
# @router.get('/v1/identity/list')
# async def identity_list(
#     token_str: str,
#     dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
# ):
#     """List all identities associated with a profile."""
#     token = util.old_token.OldToken()
#     token.from_auth_token(token_str)
#     identity_list = []
#     for identity_row in await dbi.get_profile_list(token.uid):
#         identity_list.append(identity_row.as_dict())
#     return starlette.responses.Response(util.pretty.to_pretty_json(identity_list))
