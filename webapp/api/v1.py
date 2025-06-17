import fastapi
import psycopg.errors
import sqlalchemy.exc
import starlette.requests
import starlette.responses

import api.utils
import db.models.permission
import db.models.permission
import util.dependency
import util.exc
import util.pasta_jwt

router = fastapi.APIRouter(prefix="/v1")


@router.post('/token/{edi_id}')
async def post_token(
    edi_id: str,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    # token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """Create a new token for an existing profile.
    The token will be created with the identity that was last used to sign in.
    """
    if not edi_id:
        return starlette.responses.JSONResponse(
            status_code=400,
            content={'error': 'edi_id is required'},
        )

    identity_row = await dbi.get_identity_by_edi_id(edi_id)
    pasta_token = await util.pasta_jwt.make_jwt(dbi, identity_row)

    return starlette.responses.JSONResponse(
        status_code=200,
        content={
            'token': pasta_token,
        },
    )


@router.post('/profile')
async def post_v1_profile(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """createProfile(): Create a skeleton profile
    ./docs/api/profile.md
    """
    api_method = 'createProfile'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
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


@router.post('/resource')
async def post_v1_resource(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """createResource(): Create a resource for access control
    ./docs/api/resource.md
    """
    api_method = 'createResource'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
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
    resource_row = await dbi.get_resource_by_key(token_profile_row, key)
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
    try:
        request_dict = await api.utils.request_body_to_dict(request)
    except ValueError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Invalid JSON in request body: {e}'
        )
    # Check that the request contains the required fields
    try:
        key = request_dict['resource_key']
        principal_edi_id = request_dict['principal']
        permission_level_str = request_dict['permission']
    except KeyError as e:
        return api.utils.get_response_400_bad_request(
            # str(KeyError) is the name of the missing key in single quotes
            request,
            api_method,
            f'Missing field in request: {e}',
        )
    # Check fields
    try:
        permission_level = db.models.permission.permission_level_string_to_enum(
            permission_level_str
        )
    except ValueError as e:
        return api.utils.get_response_400_bad_request(request, api_method, str(e))
    # Check that the resource exists and is owned by the profile
    try:
        resource_row = await dbi.get_owned_resource_by_key(token_profile_row, key)
    except ValueError:
        resource_row = None
    if not resource_row:
        return api.utils.get_response_404_not_found(
            request,
            api_method,
            f'Resource does not exist, or is not owned by this profile',
            resource_key=key,
        )
    # Check that the principal exists
    principal_row = await dbi.get_principal_by_edi_id(principal_edi_id)
    if not principal_row:
        return api.utils.get_response_400_bad_request(
            request,
            api_method,
            f'Principal does not exist',
            principal=principal_edi_id,
        )
    # Check that the access control rule does not already exist
    rule_row = await dbi.get_rule(resource_row, principal_row)
    if rule_row is not None:
        return api.utils.get_response_400_bad_request(
            request,
            api_method,
            f'Rule already exists',
            resource_key=key,
            principal=principal_edi_id,
            existing_permission=db.models.permission.permission_level_enum_to_string(
                rule_row.permission
            ),
        )
    # Create the rule
    try:
        await dbi.create_or_update_permission(
            resource_row,
            principal_row,
            permission_level,
        )
    except (util.exc.AuthDBError, Exception) as e:
        return api.utils.get_response_400_bad_request(request, api_method, str(e))
    except (sqlalchemy.exc.IntegrityError, psycopg.errors.UniqueViolation):
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Rule already exists', resource_key=key
        )

    return api.utils.get_response_200_ok(
        request, api_method, 'Rule created successfully', resource_key=key
    )
