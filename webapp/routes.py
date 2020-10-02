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
from flask import Flask, make_response, redirect, render_template, request, \
    url_for
from flask_bootstrap import Bootstrap
from oauthlib.oauth2 import WebApplicationClient
import requests
import urllib.parse

from webapp.config import Config
from webapp.forms import AcceptForm
from webapp import pasta_crypto
from webapp import pasta_ldap
from webapp import pasta_token
from webapp.user_db import UserDb


logger = daiquiri.getLogger('routes: ' + __name__)

app = Flask(__name__)
app.config.from_object(Config)
bootstrap = Bootstrap(app)


@app.route('/auth/accept', methods=['GET', 'POST'])
def accept():
    uid = request.args.get('uid')
    target = request.args.get('target')
    form = AcceptForm()
    if form.validate_on_submit():
        accepted = form.accept.data
        target = form.target.data
        uid = form.uid.data
        if not accepted:
            redirect_url = f'https://{target}'
            return redirect(redirect_url)
        else:
            udb = UserDb()
            udb.set_accepted(uid=uid)
            auth_token = udb.get_token(uid=uid)
            cname = udb.get_cname(uid=uid)
            redirect_url = make_target_url(target=target, auth_token=auth_token,
                                           cname=cname)
            return redirect(redirect_url)
    elif uid is not None and target is not None:
        udb = UserDb()
        if udb.get_user(uid) is None:
            resp = 'Unknown uid'
            return resp, 400
        return render_template('accept.html', form=form, uid=uid, target=target)
    else:
        resp = 'Form requires uid and target parameters to be valid'
        return resp, 400


@app.route('/auth/login/<idp>', methods=['GET'])
def login(idp):
    target = request.args.get('target')
    if idp in ('github', 'google', 'orcid') and target is None:
        resp = f'Target parameter not set'
        return resp, 400
    if idp == 'pasta':
        authorization = request.headers.get('Authorization')
        if authorization is None:
            resp = f'No authorization header in request'
            return resp, 400
        else:
            credentials = base64.b64decode(authorization[6:]).decode('utf-8')
            uid, password = credentials.split(':')
            if pasta_ldap.bind(uid, password):
                cname = get_dn_uid(uid)
                auth_token = make_pasta_token(uid=uid, groups=Config.VETTED)
                udb = UserDb()
                udb.set_user(uid=uid, token=auth_token, cname=cname)
                privacy_accepted = udb.get_accepted(uid=uid)
                if privacy_accepted:
                    response = make_response()
                    response.set_cookie('auth-token', auth_token)
                    return response
                else:
                    resp = 'I\'m a teapot, coffee is ready!'
                    return resp, 418
            else:
                resp = f'Authentication failed for user: {uid}'
                return resp, 401

    elif idp == 'google':
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
        github_client_id, _ = \
            get_github_client_info(target=target,
                                   request_base_url=request.base_url)
        client = WebApplicationClient(github_client_id)
        authorization_endpoint = Config.GITHUB_AUTH_ENDPOINT
        redirect_uri = f'{request.base_url}/callback/{target}'
        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=redirect_uri,
            scope=["user"],
        )
        return redirect(request_uri)

    elif idp == 'orcid':
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
    github_client_id, github_client_secret = \
        get_github_client_info(target=target, request_base_url=request.base_url)
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
    uid = userinfo_response['html_url']
    if 'name' in userinfo_response:
        cname = userinfo_response['name']
    else:
        cname = userinfo_response['login']

    auth_token = make_pasta_token(uid=uid, groups=Config.AUTHENTICATED)

    udb = UserDb()
    udb.set_user(uid=uid, token=auth_token, cname=cname)
    privacy_accepted = udb.get_accepted(uid=uid)
    if privacy_accepted:
        redirect_url = make_target_url(target, auth_token, cname)
        return redirect(redirect_url)
    else:
        redirect_url = f'/auth/accept?uid={uid}&target={target}'
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
        uid = userinfo_response.json()['email']
        picture = userinfo_response.json()['picture']
        given_name = userinfo_response.json()['given_name']
        sur_name = userinfo_response.json()['family_name']
        cname = f'{given_name} {sur_name}'
        groups = Config.AUTHENTICATED
    else:
        uid = Config.PUBLIC
        cname = Config.PUBLIC
        groups = ''

    auth_token = make_pasta_token(uid=uid, groups=groups)

    udb = UserDb()
    udb.set_user(uid=uid, token=auth_token, cname=cname)
    privacy_accepted = udb.get_accepted(uid=uid)
    if privacy_accepted:
        redirect_url = make_target_url(target, auth_token, cname)
        return redirect(redirect_url)
    else:
        redirect_url = f'/auth/accept?uid={uid}&target={target}'
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
    cname = token_response['name']
    uid = Config.ORCID_DNS + token_response['orcid']

    auth_token = make_pasta_token(uid=uid, groups=Config.AUTHENTICATED)

    udb = UserDb()
    udb.set_user(uid=uid, token=auth_token, cname=cname)
    privacy_accepted = udb.get_accepted(uid=uid)
    if privacy_accepted:
        redirect_url = make_target_url(target, auth_token, cname)
        return redirect(redirect_url)
    else:
        redirect_url = f'/auth/accept?uid={uid}&target={target}'
        return redirect(redirect_url)


@app.route('/auth/show_me', methods=['GET'])
def show_me():
    uid = request.args['uid']
    return uid


def get_github_client_info(target: str, request_base_url: str) -> tuple:
    if request_base_url.startswith('https://localhost:5000'):
        return Config.GITHUB_CLIENT_ID_LOCALHOST, \
               Config.GITHUB_CLIENT_SECRET_LOCALHOST
    elif target == Config.PORTAL_D:
        return Config.GITHUB_CLIENT_ID_PORTAL_D, \
               Config.GITHUB_CLIENT_SECRET_PORTAL_D
    elif target == Config.PORTAL_S:
        return Config.GITHUB_CLIENT_ID_PORTAL_S, \
               Config.GITHUB_CLIENT_SECRET_PORTAL_S
    elif target == Config.PORTAL:
        return Config.GITHUB_CLIENT_ID_PORTAL, \
               Config.GITHUB_CLIENT_SECRET_PORTAL
    elif target == Config.EZEML_D:
        return Config.GITHUB_CLIENT_ID_EZEML_D, \
                Config.GITHUB_CLIENT_SECRET_EZEML_D
    elif target == Config.EZEML:
        return Config.GITHUB_CLIENT_ID_EZEML, \
                Config.GITHUB_CLIENT_SECRET_EZEML


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


def make_target_url(target: str, auth_token: str, cname: str) -> str:
    _auth_token = urllib.parse.quote(auth_token)
    _cname = urllib.parse.quote(cname)
    if target in (Config.PORTAL, Config.PORTAL_S, Config.PORTAL_D):
        url = f'https://{target}/nis/login?token={_auth_token}&cname={_cname}'
    elif target in (Config.EZEML, Config.EZEML_D):
        url = f'https://{target}/eml/auth/login?token={_auth_token}&cname={_cname}'
    return url


if __name__ == '__main__':
    app.run(ssl_context='adhoc')
