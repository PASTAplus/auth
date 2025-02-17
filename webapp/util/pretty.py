#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: pretty

:Synopsis:

:Author:
    pasta

:Created:
    2/16/25
"""
import datetime
import json
import pprint
import typing


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj)

    # def decode(self, obj):
    #     if isinstance(obj, datetime.datetime):
    #         return obj.isoformat()
    #     return super().default(obj)


# def json_loads(json_str: str) -> list | dict:
#     return json.loads(json_str, cls=CustomJSONEncoder)


def to_pretty_json(obj: list | dict) -> str:
    json_str = json.dumps(obj, indent=2, sort_keys=True, cls=CustomJSONEncoder)
    # print(json_str)
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
