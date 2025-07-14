"""Tests for v1 isAuthorized API
"""

import logging

import pytest
import starlette.status

import db.db_interface
import db.models.permission
import db.models.permission
import tests.utils

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(100),
]


async def test_is_authorized_anon(anon_client):
    """isAuthorized()
    No token -> 401 Unauthorized
    """
    status_code = _is_authorized(
        anon_client, 'a-resource-key', db.models.permission.PermissionLevel.READ
    )
    assert status_code == starlette.status.HTTP_401_UNAUTHORIZED


async def test_invalid_permission_level(john_client):
    """isAuthorized()
    Invalid permission level -> 400 Bad Request
    """
    status_code = _is_authorized(john_client, 'a-resource-key', 'invalid-permission-level')
    assert status_code == starlette.status.HTTP_400_BAD_REQUEST


async def test_is_authorized_with_valid_token(populated_dbi, john_client, john_profile_row):
    """isAuthorized()
    Valid token and resource_key -> 200 OK with permission level.
    """
    # John creates a resource with WRITE permission
    await _new_resource(
        populated_dbi,
        john_profile_row,
        'a-resource-key-2',
        db.models.permission.PermissionLevel.WRITE,
    )
    # John is authorized at WRITE level
    assert (
        _is_authorized(john_client, 'a-resource-key-2', db.models.permission.PermissionLevel.WRITE)
        == starlette.status.HTTP_200_OK
    )
    # await _create_resource(populated_dbi, 'a-resource-key')
    # # John is authorized at CHANGE level by default, as the creator of the resource
    # assert (
    #     _call_is_authorized(john_client, 'a-resource-key', PermissionLevel.CHANGE)
    #     == starlette.status.HTTP_200_OK
    # )

    # resource_key = 'a-resource-key'
    # permission_level = PermissionLevel.READ
    # response = _call_is_authorized(john_client, resource_key, permission_level)
    # assert response.status_code == starlette.status.HTTP_200_OK
    # response_dict = response.json()
    # assert response_dict['resource_key'] == resource_key
    # assert response_dict[
    #     'permission_level'
    # ] == db.models.permission.permission_level_enum_to_string(permission_level)


def _is_authorized(client, resource_key, permission_level):
    """Call the isAuthorized endpoint
    # /resource/authorized/{permission_level}/{resource_key:path}
    """
    try:
        permission_level_str = db.models.permission.permission_level_enum_to_string(
            permission_level
        )
    except KeyError:
        permission_level_str = permission_level
    endpoint_str = f'/v1/resource/authorized/{permission_level_str}/{resource_key}'
    log.debug('Calling isAuthorized endpoint: %s', endpoint_str)
    response = client.get(endpoint_str)
    log.debug('Response status code: %s', response.status_code)
    log.debug('Response body:')
    try:
        response.json()
        tests.utils.dump_json_with_syntax_highlighting(response.text)
    except ValueError:
        log.debug(response.text)
    return response.status_code


async def _new_resource(
    populated_dbi,
    profile_row,
    resource_key,
    permission_level,
    parent_key=None,
):
    """The regular createResource() endpoint always creates a resource with the creator's profile,
    and gives the creator CHANGE permission by default. This is a more flexible version for testing.
    """
    resource_row = await populated_dbi.create_resource(
        parent_key, resource_key, label='unset', type_str='unset'
    )
    await populated_dbi.flush()
    return await populated_dbi.create_or_update_rule(
        resource_row, profile_row.principal, permission_level
    )
