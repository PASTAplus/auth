"""EDI-ID generation and validation utilities."""

import hashlib
import uuid
import re


def get_edi_id(idp_uid):
    return f'EDI-{hashlib.sha256(idp_uid.encode()).hexdigest().lower()[:40]}'


def get_random_edi_id():
    return get_edi_id(uuid.uuid4().hex)


def is_valid_edi_id(edi_id):
    return re.fullmatch(r'EDI-[a-f0-9]{40}', edi_id) is not None
