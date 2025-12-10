"""Token API v1: Manage EDI tokens
Docs:./docs/api/token.md
"""
import fastapi
import sqlalchemy.exc
import starlette.requests
import starlette.status

import api.utils
import db.models.profile
import util.dependency
import util.edi_token
import util.exc
import util.old_token
from config import Config

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
    # Create the tokens
    if key_row.group is not None:
        # Create a group EDI token
        edi_token = await util.edi_token.create_by_group(key_row.group)
        # We don't have a way to represent group-based keys in the PASTA token, so we create a
        # generic public PASTA token.
        old_token = util.old_token.make_old_token(uid='public')
    else:
        # Create a profile EDI token
        edi_token = await util.edi_token.create(dbi, key_row.profile)
        # Create a PASTA token
        old_token = util.old_token.make_old_token(
            uid=(
                key_row.profile.email
                if key_row.profile.idp_name == db.models.profile.IdpName.GOOGLE
                else key_row.profile.idp_uid
            ),
            groups=(
                Config.VETTED
                if key_row.profile.idp_name == db.models.profile.IdpName.LDAP
                else Config.AUTHENTICATED
            ),
        )

    return api.utils.get_response_200_ok(
        request,
        api_method,
        'Token created successfully',
        **{
            'pasta-token': old_token,
            'edi-token': edi_token,
        },
    )
