"""This is the main entry point for the web application, for development and testing.

See wsgi.py for the main entry point for production.
"""
import daiquiri
import uvicorn

from config import Config
import app

daiquiri.setup(
    level=Config.LOG_LEVEL,
    outputs=(
        daiquiri.output.File(Config.LOG_PATH),
        'stdout',
    ),
)

if __name__ == "__main__":
    uvicorn.run(
        app.app,
        host='127.0.0.1',
        port=5443,
        ssl_keyfile=Config.TLS_KEY_PATH,
        ssl_certfile=Config.TLS_CERT_PATH,
    )
