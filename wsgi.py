"""This is the main entry point for the web application, for production.

See run.py for the main entry point for development and testing.
"""
import os

import daiquiri

from webapp.main import app
from webapp.config import Config

cwd = os.path.dirname(os.path.realpath(__file__))
logfile = cwd + '/auth.log'
daiquiri.setup(
    level=Config.LEVEL,
    outputs=(
        daiquiri.output.File(logfile),
        'stdout',
    ),
)
log = daiquiri.getLogger(__name__)


if __name__ == '__main__':
    app.run()
