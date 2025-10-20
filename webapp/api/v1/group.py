"""Group API v1: Manage groups and group members
"""

import fastapi
import sqlalchemy.exc
import starlette.requests
import starlette.responses

import api.utils
import db.models.permission
import db.models.permission
import util.dependency
import util.url

router = fastapi.APIRouter(prefix='/v1')


@router.post('/group')
async def post_v1_group(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """createGroup(): Create a new group of EDI user profiles.
    ./docs/api/group.md
    """
    api_method = 'createGroup'
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
        title = request_dict['title']
        description = request_dict['description']
    except KeyError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Missing field in JSON in request body: {e}'
        )
    # Create the group
    new_group_row, new_resource_row = await dbi.create_group(token_profile_row, title, description)
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Group created successfully',
        group_edi_id=new_group_row.edi_id,
    )


@router.get('/group/{group_edi_id}')
async def get_v1_group(
    group_edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """readGroup(): Retrieve the title, description and member list of a group.
    ./docs/api/group.md
    """
    api_method = 'readGroup'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that the group exists
    try:
        group_row = await dbi.get_group(group_edi_id)
    except sqlalchemy.exc.NoResultFound:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Group does not exist', group=group_edi_id
        )
    # Get member list
    member_list = await dbi.get_group_member_list(token_profile_row, group_row.id)
    member_list.sort(key=lambda x: x.profile.edi_id)

    # Return the group information
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Group retrieved successfully',
        group_edi_id=group_row.edi_id,
        title=group_row.name,
        description=group_row.description,
        members=[member_row.profile.edi_id for member_row in member_list],
    )


@router.delete('/group/{group_edi_id}')
async def delete_v1_group(
    group_edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """deleteGroup(): Delete a group of EDI user profiles.
    ./docs/api/group.md
    """
    api_method = 'deleteGroup'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that the group exists
    try:
        group_row = await dbi.get_group(group_edi_id)
    except sqlalchemy.exc.NoResultFound:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Group does not exist', group=group_edi_id
        )
    # Check that the token profile has write permission for the group
    if not await dbi.is_authorized(
        token_profile_row,
        await dbi.get_group_resource(group_row),
        db.models.permission.PermissionLevel.WRITE,
    ):
        return api.utils.get_response_403_forbidden(
            request,
            api_method,
            "Must have 'write' permission to delete group",
            group=group_edi_id,
        )
    # Delete the group
    await dbi.delete_group(token_profile_row, group_row.id)
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Group deleted successfully',
        group=group_edi_id,
    )


@router.post('/group/{group_edi_id}/{profile_edi_id}')
async def post_v1_group_member(
    group_edi_id: str,
    profile_edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """addGroupMember(): Add an EDI user profile to a group
    ./docs/api/group.md
    """
    api_method = 'addGroupMember'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that the group exists
    try:
        group_row = await dbi.get_group(group_edi_id)
    except sqlalchemy.exc.NoResultFound:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Group does not exist', group=group_edi_id
        )
    # Check that the token profile has write permission for the group
    if not await dbi.is_authorized(
        token_profile_row, group_row, db.models.permission.PermissionLevel.WRITE
    ):
        return api.utils.get_response_403_forbidden(
            request,
            api_method,
            "Must have 'write' permission to add members to group",
            group=group_edi_id,
        )
    # Check that the profile exists
    try:
        profile_row = await dbi.get_profile(profile_edi_id)
    except sqlalchemy.exc.NoResultFound:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Profile does not exist', profile=profile_edi_id
        )
    # Check that the profile is not already a member of the group
    if await dbi.is_group_member(profile_row, group_row):
        return api.utils.get_response_200_ok(
            request,
            api_method,
            'User profile is already a member of the group',
            group=group_edi_id,
            profile=profile_edi_id,
        )
    # Add the profile to the group
    await dbi.add_group_member(token_profile_row, group_row.id, profile_row.id)
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Group membership added successfully',
        group=group_edi_id,
        profile=profile_edi_id,
    )


@router.delete('/group/{group_edi_id}/{profile_edi_id}')
async def delete_v1_group_member(
    group_edi_id: str,
    profile_edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """removeGroupMember(): Remove an EDI user profile from a group
    ./docs/api/group.md
    """
    api_method = 'removeGroupMember'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that the group exists
    try:
        group_row = await dbi.get_group(group_edi_id)
    except sqlalchemy.exc.NoResultFound:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Group does not exist', group=group_edi_id
        )
    # Check that the token profile has write permission for the group
    if not await dbi.is_authorized(
        token_profile_row, group_row, db.models.permission.PermissionLevel.WRITE
    ):
        return api.utils.get_response_403_forbidden(
            request,
            api_method,
            "Must have 'write' permission to remove members from group",
            group=group_edi_id,
        )
    # Check that the profile exists
    try:
        profile_row = await dbi.get_profile(profile_edi_id)
    except sqlalchemy.exc.NoResultFound:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Profile does not exist', profile=profile_edi_id
        )
    # Check that the profile is a member of the group
    if not await dbi.is_group_member(profile_row, group_row):
        return api.utils.get_response_404_not_found(
            request,
            api_method,
            'User profile is not a member of the group',
            group=group_edi_id,
            profile=profile_edi_id,
        )
    # Remove the profile from the group
    await dbi.delete_group_member(token_profile_row, group_row.id, profile_row.id)
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Group membership removed successfully',
        group=group_edi_id,
        profile=profile_edi_id,
    )
