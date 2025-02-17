import daiquiri
from ldap3 import Server, Connection, ALL

from config import Config

log = daiquiri.getLogger(__name__)


def bind(dn: str, password: str):
    result = False
    host = None
    for rdn in Config.LDAP_DOMAIN_DICT:
        if rdn in dn:
            host = Config.LDAP_DOMAIN_DICT[rdn]
    if host is not None:
        try:
            server = Server(host, use_ssl=True, get_info=ALL)
            conn = Connection(
                server=server,
                user=dn,
                password=password,
                auto_bind=True,
                receive_timeout=30,
            )
            found = conn.search(dn, '(objectclass=person)')
            if found:
                for entry in conn.entries:
                    entry_dn = entry.entry_dn
                    if entry_dn == dn:
                        result = True
                    else:
                        log.error(f'Case mismatch for {dn} and {entry_dn}')
            conn.unbind()
        except Exception as e:
            log.error(e)
    else:
        log.error(f'Unknown LDAP host for dn: {dn}')
    return result
