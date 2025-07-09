"""Tests for v1 isAuthorized API
"""

import pytest
import db.models.permission
import starlette.status

import logging
import tests.utils

import db.db_interface

from db.models.permission import PermissionLevel

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(100),
]


async def test_is_authorized_anon(anon_client):
    """isAuthorized()
    No token -> 401 Unauthorized
    """
    response = _is_authorized(anon_client, 'a-resource-key', PermissionLevel.READ)
    assert response.status_code == starlette.status.HTTP_401_UNAUTHORIZED


async def test_invalid_permission_level(john_client):
    """isAuthorized()
    Invalid permission level -> 400 Bad Request
    """
    response = _is_authorized(john_client, 'a-resource-key', 'invalid-permission-level')
    assert response.status_code == starlette.status.HTTP_400_BAD_REQUEST


async def test_is_authorized_with_valid_token(populated_dbi, john_client, john_profile_row):
    """isAuthorized()
    Valid token and resource_key -> 200 OK with permission level.
    """
    # John creates a resource with WRITE permission
    await _new_resource(populated_dbi, john_profile_row, 'a-resource-key-2', PermissionLevel.WRITE)
    # John is authorized at WRITE level
    assert (
        _is_authorized(john_client, 'a-resource-key-2', PermissionLevel.WRITE)
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
        tests.utils.dump_colored_json(response.text)
    except ValueError:
        log.debug(response.text)
    return response.status_code


async def _new_resource(
    populated_dbi,
    profile_row,
    resource_key,
    permission_level,
    resource_label=None,
    resource_type=None,
    parent_key=None,
):
    """The regular createResource() endpoint always creates a resource with the creator's profile,
    and gives the creator CHANGE permission by default. This is a more flexible version for testing.
    """
    resource_row = await _create_resource(
        populated_dbi, resource_key, resource_label, resource_type, parent_key
    )
    await _create_permission(populated_dbi, resource_row, profile_row, permission_level)


async def _create_resource(
    populated_dbi: db.db_interface.DbInterface,
    resource_key,
    resource_label=None,
    resource_type=None,
    parent_key=None,
):
    return await populated_dbi.create_resource(
        parent_key, resource_key, resource_label or 'unset', resource_type or 'unset'
    )


async def _create_permission(populated_dbi, resource_row, profile_row, permission_level):
    return await populated_dbi.create_or_update_permission(
        resource_row, profile_row, permission_level
    )
