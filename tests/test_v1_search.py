"""Tests for v1 profile management APIs"""

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
# searchPrincipals()
#


async def test_search_principals_anon(anon_client):
    """searchPrincipals()
    Missing token -> 401 Unauthorized.
    """
    response = anon_client.get('/v1/search?s=john')
    assert response.status_code == starlette.status.HTTP_401_UNAUTHORIZED


async def test_search_principals_invalid_params_1(john_client):
    """searchPrincipals()
    Invalid params (neither profiles nor groups selected) -> 400 Bad Request
    """
    response = john_client.get(
        '/v1/search', params={'s': 'john', 'profiles': 'false', 'groups': 'false'}
    )
    assert response.status_code == starlette.status.HTTP_400_BAD_REQUEST
    tests.sample.assert_match(response.json(), 'search_principals_invalid_params_1.json')


async def test_search_principals_invalid_params_2(john_client):
    """searchPrincipals()
    Invalid params (invalid true/false string) -> 400 Bad Request
    """
    response = john_client.get('/v1/search', params={'s': 'john', 'profiles': 'INVALID'})
    assert response.status_code == starlette.status.HTTP_400_BAD_REQUEST
    tests.sample.assert_match(response.json(), 'search_principals_invalid_params_2.json')


async def test_search_principals_invalid_params_3(john_client):
    """searchPrincipals()
    Invalid params (missing search string) -> 400 Bad Request
    """
    response = john_client.get('/v1/search')
    assert response.status_code == starlette.status.HTTP_400_BAD_REQUEST
    tests.sample.assert_match(response.json(), 'search_principals_invalid_params_3.json')


async def test_search_principals_authenticated(john_client):
    """searchPrincipals()
    Successful call -> 200 with valid JSON response
    """
    response = john_client.get('/v1/search', params={'s': 'john'})
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_match(response.json(), 'search_principals_authenticated.json')


async def test_search_principals_by_edi_id(john_client):
    """searchPrincipals()
    Search by EDI-ID (with and without 'EDI-' prefix) -> 200 with valid JSON response
    """
    response = john_client.get('/v1/search', params={'s': 'EDI-147d'})
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_match(response.json(), 'search_principals_by_edi_id_1.json')

    response = john_client.get('/v1/search', params={'s': '147d'})
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_match(response.json(), 'search_principals_by_edi_id_2.json')


async def test_search_principals_by_email(john_client):
    """searchPrincipals()
    Search by email -> 200 with valid JSON response
    """
    response = john_client.get('/v1/search', params={'s': 'jane@'})
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_match(response.json(), 'search_principals_by_email.json')


async def test_search_principals_by_description(john_client):
    """searchPrincipals()
    Search by group description -> 200 with valid JSON response
    """
    response = john_client.get('/v1/search', params={'s': 'Jane\'s group'})
    assert response.status_code == starlette.status.HTTP_200_OK
    tests.sample.assert_match(response.json(), 'search_principals_by_description.json')
