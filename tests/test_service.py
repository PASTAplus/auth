import json
import pprint

import pytest
import sqlalchemy
import starlette.status

import db.models.profile
import sample
import tests.utils
import db.resource_tree
import db.models.permission
import sqlalchemy.ext.asyncio

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


