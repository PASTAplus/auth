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
from flask import Flask, make_response, request

from webapp.config import Config
from webapp import pasta_crypto
from webapp import pasta_ldap
from webapp import pasta_token


logger = daiquiri.getLogger('routes: ' + __name__)

app = Flask(__name__)
app.config.from_object(Config)

@app.route('/auth/login', methods=['POST'])
def login():
    authorization = request.headers.get('Authorization')
    credentials = base64.b64decode(authorization.strip('Basic ')).decode('utf-8')
    dn, password = credentials.split(':')

    if pasta_ldap.bind(dn, password):
        token = pasta_token.PastaToken()
        token.uid = dn
        token.system = Config.SYSTEM
        token.groups = Config.AUTH_GROUP
        private_key = pasta_crypto.import_key(Config.PRIVATE_KEY)
        auth_token = pasta_crypto.create_authtoken(private_key, token.to_string())
        resp = make_response()
        resp.set_cookie('auth-token', auth_token)
        return resp
    else:
        resp = f'Authentication failed for user: {dn}'
        return resp, 401


def main():
    return 0


if __name__ == "__main__":
    main()
