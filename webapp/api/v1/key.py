"""Token API v1: Manage EDI tokens
Docs:./docs/api/token.md
"""

import fastapi
import sqlalchemy.exc
import starlette.requests
import starlette.status

import api.utils
import util.dependency
import util.edi_token
import util.exc

router = fastapi.APIRouter(prefix='/v1')

@router.post('/key')
async def post_token_key(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
):
    """Create a token for an API key."""
    api_method = 'getTokenByKey'
    # Check that the request body is valid JSON
    try:
        request_dict = await api.utils.request_body_to_dict(request)
    except ValueError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Invalid JSON in request body: {e}'
        )
    # Check that the request contains the required fields
    try:
        secret_str = request_dict['key']
    except KeyError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Missing field in JSON in request body: {e}'
        )
    # Validate the key and get the associated group or profile
    try:
        key_row = await dbi.get_valid_key(secret_str)
    except sqlalchemy.exc.NoResultFound:
        return api.utils.get_response_401_unauthorized(request, api_method, 'Invalid API key')
    # Create the EDI token
    if key_row.group is not None:
        edi_token = await util.edi_token.create_by_group(key_row.group)
    else:
        edi_token = await util.edi_token.create(dbi, key_row.profile)
    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Token created successfully',
        **{
            'edi-token': edi_token,
        },
    )
