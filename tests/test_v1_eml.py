"""Tests for v1 EML API endpoints.
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
        },
    )
    assert response.status_code == starlette.status.HTTP_403_FORBIDDEN


async def test_add_eml_vetted(populated_dbi, service_profile_row, john_client, john_profile_row):
    """addEML()
    Call with a valid EML document and vetted profile -> A set of new resources and permissions
    created to represent all the data entities in the EML document.
    """
    # Add John to the Vetted system group.
    await populated_dbi.add_group_member(
        service_profile_row, (await populated_dbi.get_vetted_group()).id, john_profile_row.id
    )
    await populated_dbi.flush()
    assert await populated_dbi.is_vetted(john_profile_row)

    response = john_client.post(
        '/v1/eml',
        json={
            'eml': tests.utils.load_test_file('icarus.3.1.xml'),
        },
    )

    assert response.status_code == starlette.status.HTTP_200_OK


# async def test_add_eml_1(populated_dbi, john_client):
#     print(await populated_dbi.get_all_profiles())
