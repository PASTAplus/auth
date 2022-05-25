# -*- coding: utf-8 -*-

""":Mod: run

:Synopsis:

:Author:
    servilla

:Created:
    2/15/18
"""
from webapp.routes import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', ssl_context="adhoc")
