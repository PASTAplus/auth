"""This is the main entry point for the web application, for development and testing.

See wsgi.py for the main entry point for production.
"""
import pathlib

import daiquiri

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
    app.run(
        # host='0.0.0.0',
        host='127.0.0.1',
        port=5000,
        debug=True,
        # ssl_context="adhoc",
        # ssl_context=(
        #     pathlib.Path('~/certificates/localhost.crt').expanduser(),
        #     pathlib.Path('~/certificates/localhost.key').expanduser(),
        # ),
    )
