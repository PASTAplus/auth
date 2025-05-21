"""This is the main entry point for the web application, for production.

See run.py for the main entry point for development and testing.
"""
import daiquiri

from config import Config
from main import app

daiquiri.setup(
    level=Config.LOG_LEVEL,
    outputs=(
        daiquiri.output.File(Config.LOG_PATH),
        'stdout',
    ),
)

if __name__ == '__main__':
    app.run()
