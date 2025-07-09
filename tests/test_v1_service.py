"""Tests for v1 service.xml management APIs
"""

import pytest

import util.service

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(100),
]

async def test_1(client):
    await util.service.print_service_xml()


async def test_2(dbi):
    await dbi.create_skeleton_profile_and_identity('106181686037612928633')
    # await util.service.print_service_xml()


