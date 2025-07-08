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
import util.exc
import util.pasta_jwt
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
        key = request_dict['resource_key']
        label = request_dict['resource_label']
        type_str = request_dict['resource_type']
        parent_key = request_dict['parent_resource_key']
    except KeyError as e:
        return api.utils.get_response_400_bad_request(
            # str(KeyError) is the name of the missing key in single quotes
            request,
            api_method,
            f'Missing field in request: {e}',
        )
    # If the parent resource key is provided, check that it exists and is owned by the profile
    parent_id = None
    if parent_key:
        try:
            parent_row = await dbi.get_owned_resource_by_key(token_profile_row, parent_key)
            parent_id = parent_row.id
        except ValueError:
            return api.utils.get_response_400_bad_request(
                request,
                api_method,
                f'Parent resource does not exist, or is not owned by this profile',
                parent_resource_key=parent_key,
            )
    # Check that the resource does not already exist
    resource_row = await dbi.get_resource_by_key(key)
    if resource_row:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Resource already exists', resource_key=key
        )
    # Create the resource and set caller as owner
    try:
        principal_row = await dbi.get_principal_by_subject(
            token_profile_row.id, db.models.permission.SubjectType.PROFILE
        )
        resource_row = await dbi.create_resource(parent_id, key, label, type_str)
        await dbi.create_or_update_permission(
            resource_row,
            principal_row,
            db.models.permission.PermissionLevel.CHANGE,
        )
    except (util.exc.AuthDBError, Exception) as e:
        return api.utils.get_response_400_bad_request(request, api_method, str(e))

    return api.utils.get_response_200_ok(
        request, api_method, 'Resource created successfully', resource_key=key
    )


# GET : /auth/v1/resource/<resource_key>?(descendants|ancestors|all))
#
# 1. "descendants" and "ancestors" together are equivalent to "all"
# 2. "all" supersedes "descendants" or "ancestors"
#
# readResource(jwt_token, resource_key, (descendants|ancestors|all))
#     jwt_token: the token of the requesting client
#     resource_key: the unique resource key of the resource
#     descendants: boolean if resource structure contains descendants (optional)
#     ancestor: boolean if resource structure contains ancestors (optional)
#     all: boolean if resource structure contains full tree (optional)
#     return:
#         200 OK if successful
#         400 Bad Request if resource is invalid
#         401 Unauthorized if the client does not provide a valid authentication token
#         403 Forbidden if client is not authorized to execute method or access resource
#         404 If resource is not found
#     body:
#         The resource structure if 200 OK, error message otherwise
#     permissions:
#         authenticated: changePermission


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
    # Retrieve if exists
    resource_row = await dbi.get_resource_by_key(resource_key)
    if not resource_row:
        return api.utils.get_response_404_not_found(request, api_method, resource_key=resource_key)
    # Check permission
    if not await dbi.is_authorized(
        token_profile_row, resource_row, db.models.permission.PermissionLevel.READ
    ):
        return api.utils.get_response_403_forbidden(request, api_method, resource_key=resource_key)
    # Success
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Resource retrieved successfully',
        key=resource_row.key,
        parent_key=resource_row.parent.key if resource_row.parent else None,
        label=resource_row.label,
        type=resource_row.type,
    )


@router.get('/resource/tree/{resource_key:path}')
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
        return api.utils.get_response_404_not_found(request, api_method, resource_key=resource_key)
    # Check permission
    if not await dbi.is_authorized(
        token_profile_row, resource_row, db.models.permission.PermissionLevel.READ
    ):
        return api.utils.get_response_403_forbidden(request, api_method, resource_key=resource_key)
    # Find all ancestors and descendants of the resource
    resource_id_list = []
    for ancestor_id in await dbi.get_resource_ancestors(token_profile_row, [resource_id.id]):
        resource_id_list.append(ancestor_id)
    for descendant_id in await dbi.get_resource_descendants(token_profile_row, [resource_id.id]):
        resource_id_list.append(descendant_id)
    resource_list = [r async for r in dbi.get_permission_generator(resource_id_list)]
    resource_tree = db.resource_tree.get_resource_tree_for_api(resource_list)

    # pprint.pp(resource_tree)
    # log.error(json.dumps(resource_tree, indent=2))
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Resource tree retrieved successfully',
        tree=resource_tree,
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
    # Check that the resource exists
    resource_row = await dbi.get_resource_by_key(resource_key)
    if not resource_row:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Resource not found', resource_key=resource_key
        )
    # Update the resource fields
    try:
        updated_fields = {}
        if 'resource_label' in request_dict:
            updated_fields['label'] = request_dict['resource_label']
        if 'resource_type' in request_dict:
            updated_fields['type'] = request_dict['resource_type']

        if not updated_fields:
            return api.utils.get_response_400_bad_request(
                request, api_method, 'No valid fields provided for update'
            )

        await dbi.update_resource(resource_key, **updated_fields)
    except (util.exc.AuthDBError, Exception) as e:
        return api.utils.get_response_400_bad_request(request, api_method, str(e))

    return api.utils.get_response_200_ok(
        request, api_method, 'Resource updated successfully', resource_key=resource_key
    )


@router.put('/resource/{resource_key:path}')
async def update_v1_profile(
    edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """updateProfile(): Update an existing profile"""
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
    # Check that the resource exists
    resource_row = await dbi.get_resource(edi_id)
    if not resource_row:
        return api.utils.get_response_404_not_found(
            request,
            api_method,
            f'Resource does not exist',
            edi_id=edi_id,
        )
    # Check that the requester is the owner of the resource
    if token_profile_row.edi_id != edi_id:
        return api.utils.get_response_403_forbidden(
            request,
            api_method,
            'You do not have permission to update this resource',
            edi_id=edi_id,
        )
    # Update the resource fields
    try:
        updated_fields = {}
        if 'common_name' in request_dict:
            updated_fields['common_name'] = request_dict['common_name']
        if 'email' in request_dict:
            updated_fields['email'] = request_dict['email']
        if not updated_fields:
            return api.utils.get_response_400_bad_request(
                request, api_method, 'Must provide common_name and/or email to update resource'
            )
        await dbi.update_resource(token_profile_row, **updated_fields)
    except (util.exc.AuthDBError, Exception) as e:
        return api.utils.get_response_400_bad_request(request, api_method, str(e))
    return api.utils.get_response_200_ok(
        request, api_method, 'Resource updated successfully', edi_id=edi_id, **updated_fields
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
            request, api_method, f'Resource not found', resource_key=resource_key
        )
    # Delete the resource
    try:
        await dbi.delete_resource(resource_key)
    except (util.exc.AuthDBError, Exception) as e:
        return api.utils.get_response_400_bad_request(request, api_method, str(e))

    return api.utils.get_response_200_ok(
        request, api_method, 'Resource deleted successfully', resource_key=resource_key
    )
