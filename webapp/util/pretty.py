import datetime
import json
import pprint
import typing
import xml.dom
import xml.dom.minidom
import xml.etree.ElementTree

import starlette.datastructures

import db.models.profile


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, starlette.datastructures.URL):
            return str(obj)
        elif isinstance(obj, set):
            return sorted(list(obj))
        elif isinstance(obj, db.models.permission.PermissionLevel):
            return db.models.permission.permission_level_enum_to_string(obj)
        return super().default(obj)


def to_pretty_json(obj: list | dict) -> str:
    json_str = json.dumps(obj, indent=2, sort_keys=False, cls=CustomJSONEncoder)
    return json_str


def from_json(json_str: str) -> list | dict:
    return json.loads(json_str)


def pp(obj: list | dict):
    print(pformat(obj))


def pformat(obj: list | dict):
    return pprint.pformat(obj, indent=2, sort_dicts=True)


def log_dict(logger: typing.Callable, msg: str, d: dict):
    logger(f'{msg}:')
    for k, v in d.items():
        logger(f'  {k}: {v}')


def to_pretty_xml(response_dict: dict) -> str:
    """Convert a dict to a pretty-printed XML doc."""

    def dict_to_xml(tag, d):
        parent_el = xml.etree.ElementTree.Element(tag)
        for k, v in d.items():
            child_el = xml.etree.ElementTree.SubElement(parent_el, k)
            child_el.text = str(v)
        return parent_el

    xml_el = dict_to_xml('result', response_dict)
    xml_str = xml.etree.ElementTree.tostring(xml_el, encoding='unicode')
    return (
        xml.dom.minidom.parseString(xml_str)
        .toprettyxml(indent='  ', encoding='UTF-8')
        .decode('UTF-8')
    )
