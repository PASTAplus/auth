"""Resource API v1: Manage resources for access control
Docs:./docs/api/resource.md
"""

import fastapi
import starlette.requests
import starlette.responses

import api.utils
import db.models.permission
import db.resource_tree
import util.dependency
import util.url

router = fastapi.APIRouter(prefix='/v1')


@router.post('/resource')
async def post_v1_resource(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """createResource(): Create a resource for access control"""
    api_method = 'createResource'
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
        resource_key = request_dict['resource_key']
        label = request_dict['resource_label']
        type_str = request_dict['resource_type']
        parent_key = request_dict['parent_resource_key']
    except KeyError as e:
        # str(KeyError) is the name of the missing key in single quotes
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Missing field in JSON in request body: {e}'
        )
    # Check that the resource does not already exist
    resource_row = await dbi.get_resource_by_key(resource_key)
    if resource_row:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Resource already exists', resource_key=resource_key
        )
    # Check that parent exists and is owned by the profile, if provided
    parent_id = None
    if parent_key:
        parent_row = await dbi.get_resource_by_key(parent_key)
        if not parent_row:
            return api.utils.get_response_404_not_found(
                request,
                api_method,
                f'Parent resource does not exist',
                parent_key=parent_key,
            )
        if not await dbi.is_authorized(
            token_profile_row, parent_row, db.models.permission.PermissionLevel.CHANGE
        ):
            return api.utils.get_response_403_forbidden(
                request,
                api_method,
                f'Parent resource is not owned by this profile',
                parent_key=parent_key,
            )
        parent_id = parent_row.id
    # Create the resource
    principal_row = await dbi.get_principal_by_subject(
        token_profile_row.id, db.models.permission.SubjectType.PROFILE
    )
    resource_row = await dbi.create_resource(parent_id, resource_key, label, type_str)
    # Create default CHANGE permission for the profile on the resource
    await dbi.create_or_update_permission(
        resource_row,
        principal_row,
        db.models.permission.PermissionLevel.CHANGE,
    )
    return api.utils.get_response_200_ok(
        request, api_method, 'Resource created successfully', resource_key=resource_key
    )


# isAuthorized()
@router.get('/resource/authorized/{permission_level_str}/{resource_key:path}')
async def get_v1_resource_authorized(
    permission_level_str: str,
    resource_key: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """isAuthorized(): Check if the profile is authorized to access a resource
    ./docs/api/resource.md
    """
    api_method = 'isAuthorized'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check for valid permission level string
    try:
        permission_level = db.models.permission.permission_level_string_to_enum(
            permission_level_str
        )
    except ValueError as e:
        return api.utils.get_response_400_bad_request(
            request,
            api_method,
            f'Invalid permission level: "{permission_level_str}" '
            'Mst be one of: read, write, or changePermission.',
        )
    # Check if the resource exists
    resource_row = await dbi.get_resource_by_key(resource_key)
    if not resource_row:
        return api.utils.get_response_404_not_found(
            request, api_method, 'Resource does not exist', resource_key=resource_key
        )
    # Check permission
    if not await dbi.is_authorized(token_profile_row, resource_row, permission_level):
        return api.utils.get_response_403_forbidden(
            request,
            api_method,
            'Profile lacks the requested permission for the resource',
            resource_key=resource_key,
            permission_level=permission_level_str,
        )
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Profile has the requested permission for the resource',
        resource_key=resource_key,
        permission_level=permission_level_str,
    )


@router.get('/resource/{resource_key:path}')
async def get_v1_resource(
    resource_key: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """readResource(): Retrieve a resource by its key
    ./docs/api/resource.md
    """
    api_method = 'readResource'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check if the resource exists
    resource_row = await dbi.get_resource_by_key(resource_key)
    if not resource_row:
        return api.utils.get_response_404_not_found(
            request, api_method, 'Resource does not exist', resource_key=resource_key
        )
    # Check permission
    if not await dbi.is_authorized(
        token_profile_row, resource_row, db.models.permission.PermissionLevel.READ
    ):
        return api.utils.get_response_403_forbidden(
            request,
            api_method,
            msg='Profile lacks READ permission for the resource',
            resource_key=resource_key,
        )
    # Success
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Resource retrieved successfully',
        resource_key=resource_row.key,
        parent_key=resource_row.parent.key if resource_row.parent else None,
        label=resource_row.label,
        type=resource_row.type,
    )


@router.get('/resource-tree/{resource_key:path}')
async def get_v1_resource(
    resource_key: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """readResourceTree(): Retrieve a resource tree by the key of one of its resources
    ./docs/api/resource.md
    """
    api_method = 'readResourceTree'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Retrieve if exists
    resource_row = await dbi.get_resource_by_key(resource_key)
    if not resource_row:
        return api.utils.get_response_404_not_found(
            request, api_method, 'Resource does not exist', resource_key=resource_key
        )
    # Check permission
    if not await dbi.is_authorized(
        token_profile_row, resource_row, db.models.permission.PermissionLevel.READ
    ):
        return api.utils.get_response_403_forbidden(
            request,
            api_method,
            'Profile lacks READ permission for the resource',
            resource_key=resource_key,
        )
    # Find all ancestors and descendants of the resource
    resource_id_list = []
    for ancestor_id in await dbi.get_resource_ancestors(token_profile_row, [resource_row.id]):
        resource_id_list.append(ancestor_id)
    for descendant_id in await dbi.get_resource_descendants(token_profile_row, [resource_row.id]):
        resource_id_list.append(descendant_id)
    resource_list = [r async for r in dbi.get_permission_generator(resource_id_list)]
    resource_tree = db.resource_tree.get_resource_tree_for_api(resource_list)

    # pprint.pp(resource_tree)
    # log.error(json.dumps(resource_tree, indent=2))
    return api.utils.get_response_200_ok(
        request, api_method, 'Resource tree retrieved successfully', tree=resource_tree
    )


@router.put('/resource/{resource_key:path}')
async def update_v1_resource(
    resource_key: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """updateResource(): Update an existing resource
    ./docs/api/resource.md
    """
    api_method = 'updateResource'
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
    if 'resource_label' in request_dict:
        updated_fields['label'] = request_dict['resource_label']
    if 'resource_type' in request_dict:
        updated_fields['type'] = request_dict['resource_type']
    if not updated_fields:
        return api.utils.get_response_400_bad_request(
            request,
            api_method,
            'Must provide resource_label and/or resource_type fields for update',
        )
    # Check that the resource exists
    resource_row = await dbi.get_resource_by_key(resource_key)
    if not resource_row:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Resource does not exist', resource_key=resource_key
        )
    # Update the resource
    await dbi.update_resource(resource_key, **updated_fields)
    return api.utils.get_response_200_ok(
        request, api_method, 'Resource updated successfully', resource_key=resource_key
    )


@router.delete('/resource/{resource_key:path}')
async def delete_v1_resource(
    resource_key: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """deleteResource(): Delete an existing resource
    ./docs/api/resource.md
    """
    api_method = 'deleteResource'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that the resource exists
    resource_row = await dbi.get_resource_by_key(resource_key)
    if not resource_row:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Resource does not exist', resource_key=resource_key
        )
    # Delete the resource
    await dbi.delete_resource(resource_key)
    return api.utils.get_response_200_ok(
        request, api_method, 'Resource deleted successfully', resource_key=resource_key
    )
