"""EDI-ID generation and validation utilities."""

import hashlib
import uuid
import re


def get_edi_id(idp_uid):
    """Generate an EDI-ID based on a user's IdP UID.
    - We use SHA-256 to hash the IdP UID, then take the first 40 hex characters (160 bits). This is
    safer and more future-proof than using SHA-1, which is natively 160 bits, while keeping
    the EDI-ID length manageable.
    """
    return f'EDI-{hashlib.sha256(idp_uid.encode("utf-8")).hexdigest().lower()[:40]}'


def get_random_edi_id():
    """Generate a random EDI-ID.
    - In some cases, we need EDI-IDs for profiles for which no one will ever log in, such as system
    profiles (the service itself, public access, authenticated access) and system groups (the vetted
    access group).
    - This is also used for creating EDI-IDs during tests.
    """
    return get_edi_id(uuid.uuid4().hex)


def is_well_formed_edi_id(edi_id):
    """Check if a string is a valid EDI-ID.
    - EDI-IDs are case-sensitive.
    """
    return re.fullmatch(r'EDI-[a-f0-9]{40}', edi_id) is not None

