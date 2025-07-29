"""This is the main entry point for the web application, for development and testing.

See wsgi.py for the main entry point for production.
"""

import pathlib
import sys

import daiquiri
import uvicorn

BASE_PATH = pathlib.Path(__file__).resolve().parent
sys.path.append((BASE_PATH / 'webapp').as_posix())

import config
import fastapi_app

import main

daiquiri.setup(
    level=config.Config.LOG_LEVEL,
    outputs=(
        daiquiri.output.File(config.Config.LOG_PATH),
        'stdout',
    ),
)

if __name__ == "__main__":
    uvicorn.run(
        fastapi_app.app,
        host='127.0.0.1',
        port=5443,
        ssl_keyfile=config.Config.TLS_KEY_PATH,
        ssl_certfile=config.Config.TLS_CERT_PATH,
    )
