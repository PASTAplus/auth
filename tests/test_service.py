import json
import pprint

import pytest

import util.service


@pytest.mark.skip
@pytest.mark.asyncio
async def test_1(client):
    await util.service.print_service_xml()


# @pytest.mark.skip
@pytest.mark.asyncio
async def test_2(dbi):
    await dbi.create_skeleton_profile_and_identity('106181686037612928633')
    # await util.service.print_service_xml()


