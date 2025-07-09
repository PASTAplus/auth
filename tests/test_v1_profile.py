"""Tests for v1 profile management APIs
"""

import logging
import pytest
import starlette.status

import tests.sample
import tests.edi_id
import tests.utils


log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(100),
]

#
# createProfile()
#


async def test_create_profile_anon(anon_client):
    """createProfile()
    Missing token -> 401 Unauthorized.
    """
    response = anon_client.post('/v1/profile')
    assert response.status_code == starlette.status.HTTP_401_UNAUTHORIZED


async def test_create_profile_with_valid_token(populated_dbi, service_client):
    """createProfile()
    Successful call -> A new profile with a new EDI_ID
    """
    existing_edi_id_set = {p.edi_id for p in await populated_dbi.get_all_profiles()}
    response = service_client.post(
        '/v1/profile',
        json={
            'idp_uid': 'a-non-existing-idp-uid',
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    response_dict = response.json()
    edi_id = response_dict['edi_id']
    assert edi_id not in existing_edi_id_set
    response = service_client.get(f'/v1/profile/{edi_id}')
    assert response.status_code == starlette.status.HTTP_200_OK
    response_dict = response.json()
    # We set edi_id to a fixed value here, so that the sample file does not change.
    response_dict['edi_id'] = '<Random EDI-ID'
    del response_dict['edi_id']
    tests.sample.assert_equal_json(response_dict, 'create_profile_with_valid_token.json')


async def test_create_profile_idempotency(populated_dbi, service_client):
    """createProfile()
    Idempotent: Calling the endpoint with the same idp_uid returns the same EDI-ID.
    """
    existing_edi_id_set = {p.edi_id for p in await populated_dbi.get_all_profiles()}
    log.error(sorted(existing_edi_id_set))

    idp_uid = 'a-non-existing-idp-uid'
    response = service_client.post('/v1/profile', json={'idp_uid': idp_uid})
    assert response.status_code == starlette.status.HTTP_200_OK
    response_dict = response.json()
    assert 'new profile' in response_dict['msg']
    edi_id = response_dict['edi_id']
    # Call again with the same idp_uid
    response = service_client.post('/v1/profile', json={'idp_uid': idp_uid})
    assert response.status_code == starlette.status.HTTP_200_OK
    response_dict = response.json()
    assert 'existing profile' in response_dict['msg']
    # Same EDI-ID is returned in both cases
    assert response_dict['edi_id'] == edi_id


#
# readProfile()
#


async def test_read_profile_anon(anon_client):
    """readProfile()
    No token -> 401 Unauthorized
    """
    response = anon_client.get(f'/v1/profile/{tests.edi_id.JANE}')
    assert response.status_code == starlette.status.HTTP_401_UNAUTHORIZED


async def test_read_profile_access_forbidden(john_client):
    """readProfile()
    API access denied -> 403 Forbidden
    """
    # TODO


async def test_read_profile_not_found(john_client):
    """readProfile()
    Unknown EDI-ID -> 404 Not Found
    """
    response = john_client.get(f'/v1/profile/non-existent-edi-id')
    assert response.status_code == starlette.status.HTTP_404_NOT_FOUND


async def test_read_profile_by_owner(john_client):
    """readProfile()
    Owner reads own profile -> 200 OK, all fields returned.
    """
    response = john_client.get(f'/v1/profile/{tests.edi_id.JOHN}')
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_equal_json(response.text, 'read_profile_by_owner.json')


async def test_read_profile_by_non_owner(jane_client):
    """readProfile()
    When non-owner reads another user's profile, only public fields are returned.
    """
    response = jane_client.get(f'/v1/profile/{tests.edi_id.JOHN}')
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_equal_json(response.text, 'read_profile_by_non_owner.json')


#
# updateProfile()
#


async def test_update_profile_anon(anon_client):
    """updateProfile()
    No token -> 401 Unauthorized
    """
    response = anon_client.put(f'/v1/profile/{tests.edi_id.JANE}')
    assert response.status_code == starlette.status.HTTP_401_UNAUTHORIZED


async def test_update_profile_access_forbidden(john_client):
    """updateProfile()
    API access denied -> 403 Forbidden
    """
    # TODO


async def test_update_profile_not_found(john_client):
    """updateProfile()
    Unknown EDI-ID -> 404 Not Found
    """
    response = john_client.put(
        f'/v1/profile/non-existent-edi-id',
        json={
            'common_name': 'John Smith RENAMED',
        },
    )
    assert response.status_code == starlette.status.HTTP_404_NOT_FOUND


async def test_update_profile_by_owner_with_invalid_json(john_client):
    """updateProfile()
    Owner tries to update own profile with invalid JSON -> 400 Bad Request.
    """
    response = john_client.put(
        f'/v1/profile/{tests.edi_id.JOHN}',
        data='not-a-valid-json-document',
    )
    assert response.status_code == starlette.status.HTTP_400_BAD_REQUEST


async def test_update_profile_by_non_owner(jane_client):
    """updateProfile()
    Non-owner tries to update another user's profile -> 403 Forbidden.
    """
    response = jane_client.put(
        f'/v1/profile/{tests.edi_id.JOHN}',
        json={
            'common_name': 'John Smith RENAMED',
        },
    )
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN


async def test_update_profile_by_owner(john_client):
    """updateProfile()
    Owner updates own profile -> 200 OK, profile updated.
    """
    response = john_client.put(
        f'/v1/profile/{tests.edi_id.JOHN}',
        json={
            'common_name': 'John Smith RENAMED',
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    response = john_client.get(f'/v1/profile/{tests.edi_id.JOHN}')
    assert response.status_code == starlette.status.HTTP_200_OK
    assert response.json()['common_name'] == 'John Smith RENAMED'
    tests.sample.assert_equal_json(response.text, 'update_profile_by_owner.json')


#
# deleteProfile()
#


async def test_delete_profile_anon(anon_client):
    """deleteProfile()
    No token -> 401 Unauthorized
    """
    response = anon_client.delete(f'/v1/profile/{tests.edi_id.JANE}')
    assert response.status_code == starlette.status.HTTP_401_UNAUTHORIZED


async def test_delete_profile_access_forbidden(john_client):
    """deleteProfile()
    API access denied -> 403 Forbidden
    """
    # TODO


async def test_delete_profile_not_found(john_client):
    """deleteProfile()
    Unknown EDI-ID -> 404 Not Found
    """
    response = john_client.delete(f'/v1/profile/non-existent-edi-id')
    assert response.status_code == starlette.status.HTTP_404_NOT_FOUND


async def test_delete_profile_by_non_owner(jane_client):
    """deleteProfile()
    Non-owner tries to delete another user's profile -> 403 Forbidden.
    """
    response = jane_client.delete(f'/v1/profile/{tests.edi_id.JOHN}')
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN


async def test_delete_profile_by_owner(john_client):
    """deleteProfile()
    Owner deletes own profile -> 200 OK, profile deleted.
    This also immediately invalidates the user's token, since it no longer connects to a profile.
    """
    response = john_client.delete(f'/v1/profile/{tests.edi_id.JOHN}')
    assert response.status_code == starlette.status.HTTP_200_OK
    # Since the profile is now deleted, the user's token no longer connects to a profile.
    response = john_client.get(f'/v1/profile/{tests.edi_id.JOHN}')
    assert response.status_code == starlette.status.HTTP_401_UNAUTHORIZED


async def test_delete_profile_by_owner_with_invalid_edi_id(john_client):
    """deleteProfile()
    Owner tries to delete own profile with invalid EDI-ID -> 404 Not Found.
    """
    response = john_client.delete(f'/v1/profile/invalid-edi-id')
    assert response.status_code == starlette.status.HTTP_404_NOT_FOUND


