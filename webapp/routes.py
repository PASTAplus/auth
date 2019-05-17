#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: routes

:Synopsis:

:Author:
    servilla

:Created:
    5/15/19
"""
import base64

import daiquiri
from flask import Flask, request

from webapp.config import Config
from webapp import pasta_ldap


logger = daiquiri.getLogger('routes: ' + __name__)

app = Flask(__name__)
app.config.from_object(Config)

@app.route('/auth/login', methods=['POST'])
def login():
    authorization = request.headers.get('Authorization')
    credentials = base64.b64decode(authorization.strip('Basic ')).decode('utf-8')
    dn, password = credentials.split(':')

    if pasta_ldap.bind(dn, password):
        return 'Success'
    else:
        return 'Failure'


def main():
    return 0


if __name__ == "__main__":
    main()
