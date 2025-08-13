#!/usr/bin/env python

"""Decode and print an EDI token"""
import argparse
import asyncio
import pathlib
import sys

import daiquiri

BASE_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((BASE_PATH / 'webapp').as_posix())

import util.pasta_jwt
import util.dependency

log = daiquiri.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('token', help='EDI token')
    args = parser.parse_args()

    async with util.dependency.get_dbi() as dbi:
        token_obj = await util.pasta_jwt.PastaJwt.decode(dbi, args.token)

    print(token_obj.claims_pp)


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
