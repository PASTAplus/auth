#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: bind

:Synopsis:
    Perform a bind to the given LDAP host; otherwise return an error.

:Author:
    servilla

:Created:
    5/15/2019
"""
import daiquiri
from ldap3 import Server, Connection, ALL, HASHED_SALTED_SHA, MODIFY_REPLACE

from webapp.config import Config

logger = daiquiri.getLogger('ldap_user: ' + __name__)


def bind(dn: str, password: str):
    result = False
    host = None
    for rdn in Config.DOMAINS:
        if rdn in dn:
            host = Config.DOMAINS[rdn]
    if host is not None:
        try:
            server = Server(host, use_ssl=True, get_info=ALL)
            conn = Connection(server=server, user=dn, password=password,
                              auto_bind=True, receive_timeout=30)
            result = True
            conn.unbind()
        except Exception as e:
            logger.error(e)
    else:
        logger.error(f'Unknown LDAP host for dn: {dn}')
    return result
