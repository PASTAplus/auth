# -*- coding: utf-8 -*-

""":Mod: run

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
    ssl_keyfile = '/home/servilla/git/login/webapp/certs/localhost+1-key.pem'
    ssl_certfile = '/home/servilla/git/login/webapp/certs/localhost+1.pem'
    app.run(
        host='0.0.0.0',
        port=5443,
        # ssl_context="adhoc",
        ssl_context=(ssl_certfile, ssl_keyfile)
    )
