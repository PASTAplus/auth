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
from webapp.user_db import UserDb


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
            # TODO: set_uid and set_token; test for privacy_acceptance
            udb = UserDb()
            udb.set_user(uid=dn, token=auth_token, cname=get_dn_uid(dn))
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
    elif idp == 'github':
        if target is None:
            resp = f'Target parameter not set'
            return resp, 400
        github_client_id, _ = get_github_client_info(target)
        client = WebApplicationClient(github_client_id)
        # github_provider_cfg = get_github_provider_cfg()
        authorization_endpoint = Config.GITHUB_AUTH_ENDPOINT
        redirect_uri = f'{request.base_url}/callback/{target}'
        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=redirect_uri,
            scope=["user"],
        )
        return redirect(request_uri)
    elif idp == 'orcid':
        if target is None:
            resp = f'Target parameter not set'
            return resp, 400
        orcid_client_id = Config.ORCID_CLIENT_ID
        authorization_endpoint = Config.ORCID_IMPLICIT_ENDPOINT
        redirect_uri = f'{request.base_url}/callback/{target}'
        request_uri = f'{authorization_endpoint}?client_id={orcid_client_id}' + \
                      f'&response_type=code&scope=/authenticate&' + \
                      f'redirect_uri={redirect_uri}'
        return redirect(request_uri)
    else:
        resp = f'Unknown identity provider: {idp}'
        return resp, 400


@app.route("/auth/login/github/callback/<target>", methods=['GET'])
def github_callback(target):
    code = request.args.get("code")
    github_client_id, github_client_secret = get_github_client_info(target)
    token_endpoint = Config.GITHUB_TOKEN_ENDPOINT
    client = WebApplicationClient(github_client_id)
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )
    headers["Accept"] = "application/json"
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(github_client_id, github_client_secret),
    ).json()
    access_token = token_response['access_token']
    userinfo_endpoint = f'{Config.GITHUB_USER_ENDPOINT}' + \
                        f'?access_token={access_token}'
    userinfo_response = requests.get(url=userinfo_endpoint).json()
    html_url = userinfo_response['html_url']
    auth_token = make_pasta_token(uid=html_url, groups=Config.AUTHENTICATED)
    if 'name' in userinfo_response:
        common_name = userinfo_response['name']
    else:
        common_name = userinfo_response['login']

    redirect_url = make_target_url(target,
                                   urllib.parse.quote(auth_token),
                                   urllib.parse.quote(common_name))
    # TODO: set_uid and set_token; test for privacy_acceptance
    return redirect(redirect_url)


@app.route('/auth/login/google/callback/<target>', methods=['GET'])
def google_callback(target):
    code = request.args.get('code')
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg['token_endpoint']
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
    userinfo_endpoint = google_provider_cfg['userinfo_endpoint']
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    if userinfo_response.json().get('email_verified'):
        unique_id = userinfo_response.json()['sub']
        email = userinfo_response.json()['email']
        picture = userinfo_response.json()['picture']
        given_name = userinfo_response.json()['given_name']
        sur_name = userinfo_response.json()['family_name']
        auth_token = make_pasta_token(uid=email, groups=Config.AUTHENTICATED)
        common_name = f'{given_name} {sur_name}'
    else:
        auth_token = make_pasta_token(uid=Config.PUBLIC)
        common_name = Config.PUBLIC

    redirect_url = make_target_url(target,
                                   urllib.parse.quote(auth_token),
                                   urllib.parse.quote(common_name))
    # TODO: set_uid and set_token; test for privacy_acceptance
    return redirect(redirect_url)


@app.route('/auth/login/orcid/callback/<target>', methods=['GET'])
def orcid_callback(target):
    code = request.args.get('code')
    orcid_client_id = Config.ORCID_CLIENT_ID
    orcid_client_secret = Config.ORCID_CLIENT_SECRET
    token_endpoint = Config.ORCID_TOKEN_ENDPOINT
    body = f'client_id={orcid_client_id}' + \
           f'&client_secret={orcid_client_secret}' + \
           f'&grant_type=authorization_code&code={code}' + \
           f'&redirect_uri={urllib.parse.quote(request.base_url)}'
    headers = dict()
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    headers['Accept'] = 'application/json'
    token_response = requests.post(
        token_endpoint,
        headers=headers,
        data=body,
    ).json()
    common_name = token_response['name']
    orcid = Config.ORCID_DNS + token_response['orcid']
    auth_token = make_pasta_token(uid=orcid, groups=Config.AUTHENTICATED)

    redirect_url = make_target_url(target,
                                   urllib.parse.quote(auth_token),
                                   urllib.parse.quote(common_name))
    # TODO: set_uid and set_token; test for privacy_acceptance
    return redirect(redirect_url)


@app.route('/auth/show_me', methods=['GET'])
def show_me():
    uid = request.args['uid']
    return uid


def get_github_client_info(target: str) -> tuple:
    if target == Config.DEVELOPMENT:
        return Config.GITHUB_CLIENT_ID_PORTAL_D,\
               Config.GITHUB_CLIENT_SECRET_PORTAL_D
    elif target == Config.STAGING:
        return Config.GITHUB_CLIENT_ID_PORTAL_S, \
               Config.GITHUB_CLIENT_SECRET_PORTAL_S
    elif target == Config.PRODUCTION:
        return Config.GITHUB_CLIENT_ID_PORTAL, \
               Config.GITHUB_CLIENT_SECRET_PORTAL
    else:
        return Config.GITHUB_CLIENT_ID_LOCALHOST, \
               Config.GITHUB_CLIENT_SECRET_LOCALHOST


def get_dn_uid(dn: str) -> str:
    dn_parts = dn.split(",")
    uid = dn_parts[0].split("=")[1]
    return uid


def get_github_provider_cfg():
    return requests.get(Config.GITHUB_DISCOVERY_URL).json()


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


if __name__ == '__main__':
    app.run(ssl_context='adhoc')
