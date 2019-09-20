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
import json

import daiquiri
from flask import Flask, make_response, redirect, request, url_for
from oauthlib.oauth2 import WebApplicationClient
import requests
import urllib.parse

from webapp.config import Config
from webapp import pasta_crypto
from webapp import pasta_ldap
from webapp import pasta_token


logger = daiquiri.getLogger('routes: ' + __name__)

app = Flask(__name__)
app.config.from_object(Config)


@app.route('/auth/login/<idp>', methods=['GET'])
def login(idp):
    target = request.args.get('target')
    if idp == 'pasta':
        authorization = request.headers.get('Authorization')
        if authorization is None:
            uid = Config.PUBLIC
            auth_token = make_pasta_token(uid=uid)
        else:
            credentials = base64.b64decode(authorization.strip('Basic ')).\
                decode('utf-8')
            dn, password = credentials.split(':')
            if pasta_ldap.bind(dn, password):
                auth_token = make_pasta_token(uid=dn, groups=Config.VETTED)
            else:
                resp = f'Authentication failed for user: {dn}'
                return resp, 401
        response = make_response()
        response.set_cookie('auth-token', auth_token)
        return response
    elif idp == 'google':
        if target is None:
            resp = f'Target parameter not set'
            return resp, 400
        client = WebApplicationClient(Config.GOOGLE_CLIENT_ID)
        google_provider_cfg = get_google_provider_cfg()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]
        redirect_uri = f'{request.base_url}/callback/{target}'
        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=redirect_uri,
            scope=["openid", "email", "profile"],
        )
        return redirect(request_uri)
    else:
        resp = f'Unknown identity provider: {idp}'
        return resp, 400



@app.route("/auth/login/google/callback/<target>", methods=['GET'])
def google_callback(target):
    code = request.args.get("code")
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]
    client = WebApplicationClient(Config.GOOGLE_CLIENT_ID)
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(Config.GOOGLE_CLIENT_ID, Config.GOOGLE_CLIENT_SECRET),
    )
    client.parse_request_body_response(json.dumps(token_response.json()))
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        given_name = userinfo_response.json()["given_name"]
        sur_name = userinfo_response.json()["family_name"]
        auth_token = make_pasta_token(uid=email, groups=Config.AUTHENTICATED)
        common_name = f'{given_name} {sur_name}'
    else:
        auth_token = make_pasta_token(uid=Config.PUBLIC)
        common_name = Config.PUBLIC

    redirect_url = make_target_url(target,
                                   urllib.parse.quote(auth_token),
                                   urllib.parse.quote(common_name))
    # redirect_url = f'{url_for("show_me")}?uid={users_name}'
    return redirect(redirect_url)


@app.route('/auth/show_me', methods=['GET'])
def show_me():
    uid = request.args['uid']
    return uid


def get_google_provider_cfg():
    return requests.get(Config.GOOGLE_DISCOVERY_URL).json()


def make_pasta_token(uid, groups=''):
    token = pasta_token.PastaToken()
    token.system = Config.SYSTEM
    token.uid = uid
    token.groups = groups
    private_key = pasta_crypto.import_key(Config.PRIVATE_KEY)
    auth_token = pasta_crypto.create_authtoken(private_key, token.to_string())
    return auth_token


def make_target_url(target, auth_token, common_name):
    path = Config.PORTAL_PATH
    url = f'https://{target}{path}?token={auth_token}&cname={common_name}'
    return url


if __name__ == "__main__":
    app.run(ssl_context="adhoc")
