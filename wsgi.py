# -*- coding: utf-8 -*-

""":Mod: wsgi

:Synopsis:

:Author:
    servilla

:Created:
    2/15/18
"""
import os

import daiquiri

from webapp.routes import app
from webapp.config import Config

cwd = os.path.dirname(os.path.realpath(__file__))
logfile = cwd + '/auth.log'
daiquiri.setup(level=Config.LEVEL,
               outputs=(daiquiri.output.File(logfile), 'stdout',))
logger = daiquiri.getLogger(__name__)


if __name__ == '__main__':
    app.run()
