"""This is the main entry point for the web application, for development and testing.

See wsgi.py for the main entry point for production.
"""
import daiquiri
import uvicorn

from webapp.config import Config
from webapp.main import app

daiquiri.setup(
    level=Config.LOG_LEVEL,
    outputs=(
        daiquiri.output.File(Config.LOG_PATH),
        'stdout',
    ),
)

if __name__ == "__main__":
    uvicorn.run(app,
                host='127.0.0.1',
                port=5443,
                ssl_keyfile=Config.SERVER_KEY,
                ssl_certfile=Config.SERVER_CERT
                )
