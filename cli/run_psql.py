#!/usr/bin/env python

"""Run psql using the configured database connection."""
import asyncio
import os
import pathlib
import sys

BASE_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((BASE_PATH / 'webapp').as_posix())

from config import Config


async def main():
    os.system(
        f'psql postgresql://{Config.DB_USER}:{Config.DB_PW}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}'
    )
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
