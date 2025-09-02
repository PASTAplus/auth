"""Tests for v1 EML API endpoints."""

import logging
import re

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
# addEML()
#


async def test_add_eml_not_vetted(populated_dbi, john_client):
    """addEML()
    Call with a valid EML document, but by profile that is not vetted -> 403 Forbidden
    """
    response = john_client.post(
        '/v1/eml',
        json={
            'eml': tests.utils.load_test_file('icarus.3.1.xml'),
            'key_prefix': 'https://test.example',
        },
    )
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN


async def test_add_eml_vetted(populated_dbi, service_profile_row, john_client, john_profile_row):
    """addEML()
    Call with a valid EML document and vetted profile -> A set of new resources and permissions
    created to represent all the data entities in the EML document.
    """
    # Add John to the Vetted system group.
    await tests.utils.add_vetted(populated_dbi, service_profile_row, john_profile_row)

    response = john_client.post(
        '/v1/eml',
        json={
            'eml': tests.utils.load_test_file('icarus.3.1.xml'),
            'key_prefix': 'https://test.example',
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    # populated_dbi.flush()
    response = john_client.get('/v1/resource-tree/https://test.example/package/eml/icarus/3/1')
    # tests.utils.dump_response(response)
    assert response.status_code == starlette.status.HTTP_200_OK
    response_dict = response.json()

    def _d(r):
        for k, v in r.items():
            if k == 'key' and re.match(r'[0-9a-f]{32}', v):
                r[k] = 'CLOBBERED-RANDOM-KEY'
            elif k in ('tree', 'children'):
                for child in v:
                    _d(child)

    _d(response_dict)

    tests.sample.assert_match(response_dict, 'add_eml_vetted.json')
