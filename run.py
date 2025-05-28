"""This is the main entry point for the web application, for development and testing.

See wsgi.py for the main entry point for production.
"""
import daiquiri
import uvicorn
import sys
import pathlib

ROOT_PATH = pathlib.Path(__file__).resolve().parent
sys.path.append((ROOT_PATH / 'webapp').as_posix())

from config import Config
from fastapi_app import app

daiquiri.setup(
    level=Config.LOG_LEVEL,
    outputs=(
        daiquiri.output.File(Config.LOG_PATH),
        'stdout',
    ),
)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host='127.0.0.1',
        port=5443,
        ssl_keyfile=Config.TLS_KEY_PATH,
        ssl_certfile=Config.TLS_CERT_PATH,
    )
