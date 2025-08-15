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


@router.post('/group/{group_edi_id}/{profile_edi_id}')
async def post_v1_group_member(
    group_edi_id: str,
    profile_edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """addGroupMember(): Add one or more EDI user profiles to a group
    ./docs/api/group.md
    """
    api_method = 'addGroupMember'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that the group exists
    try:
        group_row = await dbi.get_group_by_edi_id(group_edi_id)
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
    if await dbi.is_in_group(profile_row, group_row):
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
