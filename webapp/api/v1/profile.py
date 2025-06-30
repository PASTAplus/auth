"""Profile API v1
Docs:./docs/api/profile.md
"""

import fastapi
import starlette.requests
import starlette.responses

import api.utils
import util.dependency
import util.exc
import util.pasta_jwt
import util.url

router = fastapi.APIRouter(prefix='/v1')


@router.post('/profile')
async def post_v1_profile(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """createProfile(): Create a skeleton profile"""
    api_method = 'createProfile'
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
    try:
        idp_uid = request_dict['idp_uid']
    except KeyError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Missing field in request: {e}'
        )
    try:
        # Check if the identity already exists
        identity_row = await dbi.get_identity_by_idp_uid(idp_uid)
        # See README.md: Strategy for dealing with Google emails historically used as identifiers
        if not identity_row:
            identity_row = await dbi.get_identity_by_email(idp_uid)
        if identity_row:
            return api.utils.get_response_200_ok(
                request,
                api_method,
                'An existing profile was used',
                edi_id=identity_row.profile.edi_id,
            )
        # Create a new skeleton profile and identity
        identity_row = await dbi.create_skeleton_profile_and_identity(idp_uid=idp_uid)
    except (util.exc.AuthDBError, Exception) as e:
        return api.utils.get_response_400_bad_request(request, api_method, str(e))
    return api.utils.get_response_200_ok(
        request, api_method, 'A new profile was created', edi_id=identity_row.profile.edi_id
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
    #
    profile_row = await dbi.get_profile(edi_id)
    if not profile_row:
        return api.utils.get_response_404_not_found(
            request,
            api_method,
            f'Profile does not exist',
            edi_id=edi_id,
        )
    # Retrieved successfully. Return whole or partial profile, depending on whether the requester is
    # the owner of the profile.
    result_dict = dict(
        edi_id=edi_id,
        common_name=profile_row.common_name,
    )
    if token_profile_row.edi_id == edi_id:
        msg = 'Profile retrieved by owner. Private and public fields returned.'
        result_dict.update(
            dict(
                email=profile_row.email,
                avatar_url=util.url.get_abs_url(profile_row.avatar_url),
                email_notifications=profile_row.email_notifications,
                privacy_policy_accepted=profile_row.privacy_policy_accepted,
                privacy_policy_accepted_date=profile_row.privacy_policy_accepted_date,
            )
        )
    else:
        msg = 'Profile retrieved by non-owner. Only public fields returned.'
    return api.utils.get_response_200_ok(request, api_method, msg, **result_dict)


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
    # Check that the profile exists
    profile_row = await dbi.get_profile(edi_id)
    if not profile_row:
        return api.utils.get_response_404_not_found(
            request,
            api_method,
            f'Profile does not exist',
            edi_id=edi_id,
        )
    # Check that the requester is the owner of the profile
    if token_profile_row.edi_id != edi_id:
        return api.utils.get_response_403_forbidden(
            request,
            api_method,
            'You do not have permission to update this profile',
            edi_id=edi_id,
        )
    # Update the profile fields
    try:
        updated_fields = {}
        if 'common_name' in request_dict:
            updated_fields['common_name'] = request_dict['common_name']
        if 'email' in request_dict:
            updated_fields['email'] = request_dict['email']
        if not updated_fields:
            return api.utils.get_response_400_bad_request(
                request, api_method, 'Must provide common_name and/or email to update profile'
            )
        await dbi.update_profile(token_profile_row, **updated_fields)
    except (util.exc.AuthDBError, Exception) as e:
        return api.utils.get_response_400_bad_request(request, api_method, str(e))
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
    profile_row = await dbi.get_profile(edi_id)
    if not profile_row:
        return api.utils.get_response_404_not_found(
            request,
            api_method,
            f'Profile does not exist',
            edi_id=edi_id,
        )
    # Check that the requester is the owner of the profile
    if token_profile_row.edi_id != edi_id:
        return api.utils.get_response_403_forbidden(
            request,
            api_method,
            'You do not have permission to delete this profile',
            edi_id=edi_id,
        )
    # Delete the profile
    try:
        await dbi.delete_profile(token_profile_row)
    except (util.exc.AuthDBError, Exception) as e:
        return api.utils.get_response_400_bad_request(request, api_method, str(e))
    return api.utils.get_response_200_ok(
        request, api_method, 'Profile deleted successfully', edi_id=edi_id
    )
