import util
import sample
import tests.util
import pytest
import util
import fastapi
import starlette.status


def test_get_all_profiles_with_identity_mapping(db):
    db.get_collection_list(None, 'e')
