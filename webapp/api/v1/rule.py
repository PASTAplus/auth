import fastapi
import starlette.requests
import starlette.responses

import api.utils
import db.models.permission
import db.models.permission
import util.dependency
import util.url

router = fastapi.APIRouter(prefix='/v1')


@router.post('/rule')
async def post_v1_rule(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """createRule(): Create an access control rule (ACR) for a resource
    ./docs/api/rule.md
    """
    api_method = 'createRule'
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
        principal_edi_id = request_dict['principal']
        permission_level_str = request_dict['permission']
    except KeyError as e:
        return api.utils.get_response_400_bad_request(
            # str(KeyError) is the name of the missing key in single quotes
            request,
            api_method,
            f'Missing field in JSON in request body: {e}',
        )
    # Check for valid permission level string
    try:
        permission_level = db.models.permission.permission_level_string_to_enum(
            permission_level_str
        )
    except ValueError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Invalid permission level: "{permission_level_str}"'
        )
    # Check that the resource exists
    resource_row = await dbi.get_resource_by_key(resource_key)
    if not resource_row:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Resource does not exist', resource_key=resource_key
        )
    # Check that the principal exists
    principal_row = await dbi.get_principal_by_edi_id(principal_edi_id)
    if not principal_row:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Principal does not exist', principal=principal_edi_id
        )
    # Check that the access control rule does not already exist
    rule_row = await dbi.get_rule(resource_row, principal_row)
    if rule_row:
        return api.utils.get_response_400_bad_request(
            request,
            api_method,
            f'Rule already exists',
            resource_key=resource_key,
            principal=principal_edi_id,
            existing_permission=db.models.permission.permission_level_enum_to_string(
                rule_row.permission
            ),
        )
    # Create the rule
    await dbi.create_or_update_permission(resource_row, principal_row, permission_level)
    return api.utils.get_response_200_ok(
        request, api_method, 'Rule created successfully', resource_key=resource_key
    )


@router.get('/rule/{resource_key:path}/{principal}')
async def read_v1_rule(
    resource_key: str,
    principal: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """readRule(): Retrieve an access control rule (ACR) for a resource
    ./docs/api/rule.md
    """
    api_method = 'readRule'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check principal
    principal_row = await dbi.get_principal_by_edi_id(principal)
    if not principal_row:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Principal does not exist', principal=principal
        )
    # Check resource
    resource_row = await dbi.get_resource_by_key(resource_key)
    if not resource_row:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Resource does not exist', resource_key=resource_key
        )
    # Check rule
    rule_row = await dbi.get_rule(resource_row, principal_row)
    if rule_row is None:
        return api.utils.get_response_404_not_found(
            request,
            api_method,
            f'Rule does not exist',
            resource_key=resource_key,
            principal=principal,
        )
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Rule retrieved successfully',
        resource_key=resource_key,
        principal=principal,
        permission=db.models.permission.permission_level_enum_to_string(rule_row.permission),
    )


@router.put('/rule/{resource_key:path}/{principal}')
async def update_v1_rule(
    resource_key: str,
    principal: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """updateRule(): Update an access control rule (ACR) for a resource
    ./docs/api/rule.md
    """
    api_method = 'updateRule'
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
    # Check that the request contains the required field
    try:
        permission_level_str = request_dict['permission']
    except KeyError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Missing field in JSON in request body: {e}'
        )
    # Validate the permission level
    try:
        permission_level = db.models.permission.permission_level_string_to_enum(
            permission_level_str
        )
    except ValueError as e:
        return api.utils.get_response_400_bad_request(request, api_method, str(e))
    # Check that the resource exists and is owned by the profile
    try:
        resource_row = await dbi.get_owned_resource_by_key(token_profile_row, resource_key)
    except ValueError:
        resource_row = None
    if not resource_row:
        return api.utils.get_response_404_not_found(
            request,
            api_method,
            f'Resource does not exist',
            resource_key=resource_key,
        )
    # Check that the principal exists
    principal_row = await dbi.get_principal_by_edi_id(principal)
    if not principal_row:
        return api.utils.get_response_400_bad_request(
            request,
            api_method,
            f'Principal does not exist',
            principal=principal,
        )
    # Check that the rule exists
    rule_row = await dbi.get_rule(resource_row, principal_row)
    if rule_row is None:
        return api.utils.get_response_404_not_found(
            request,
            api_method,
            f'Rule does not exist',
            resource_key=resource_key,
            principal=principal,
        )
    # Update the rule
    await dbi.create_or_update_permission(resource_row, principal_row, permission_level)
    return api.utils.get_response_200_ok(
        request, api_method, 'Rule updated successfully', resource_key=resource_key
    )


@router.delete('/rule/{resource_key:path}/{principal}')
async def delete_v1_rule(
    resource_key: str,
    principal: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """deleteRule(): Delete an access control rule (ACR) for a resource
    ./docs/api/rule.md
    """
    api_method = 'deleteRule'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that the resource exists and is owned by the profile
    try:
        resource_row = await dbi.get_owned_resource_by_key(token_profile_row, resource_key)
    except ValueError:
        resource_row = None
    if not resource_row:
        return api.utils.get_response_404_not_found(
            request, api_method, f'Resource does not exist', resource_key=resource_key
        )
    # Check that the principal exists
    principal_row = await dbi.get_principal_by_edi_id(principal)
    if not principal_row:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Principal does not exist', principal=principal
        )
    # Check that the rule exists
    rule_row = await dbi.get_rule(resource_row, principal_row)
    if rule_row is None:
        return api.utils.get_response_404_not_found(
            request,
            api_method,
            f'Rule does not exist',
            resource_key=resource_key,
            principal=principal,
        )
    # Delete the rule
    await dbi.delete_rule(resource_row, principal_row)
    return api.utils.get_response_200_ok(
        request, api_method, 'Rule deleted successfully', resource_key=resource_key
    )
