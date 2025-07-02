import re

import pytest
import sqlalchemy.exc


def _check_edi_id(edi_id):
    assert re.match(r'EDI-[\da-f]{32}$', edi_id)


def test_create_db_instance(db):
    assert db is not None


def test_get_new_edi_id(db):
    edi_id = db.get_new_edi_id()
    _check_edi_id(edi_id)
