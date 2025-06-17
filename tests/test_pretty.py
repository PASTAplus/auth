"""Test util.pretty module"""

import xml.etree.ElementTree

import pytest

import sample
import util.pretty


@pytest.mark.asyncio
async def test_to_pretty_xml():
    d = {
        "method": "createProfile",
        "edi_id": "EDI-1234567890abcdef1234567890abcdef",
        "msg": "A new profile was created",
    }
    xml_output = util.pretty.to_pretty_xml(d)
    root = xml.etree.ElementTree.fromstring(xml_output)
    d_rundtrip = {child.tag: child.text for child in root}
    assert d_rundtrip == d
    sample.assert_equal(xml_output, 'to_pretty_xml.xml')

