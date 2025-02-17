from util import utils
import sample
import tests.util
import util.utils
import starlette.status


# @pytest.mark.skip
def test_ping(client):
    response = client.get('/auth/ping')
    assert response.status_code == starlette.status.HTTP_200_OK
    assert response.text == 'pong'


# @pytest.mark.skip
def test_list_profiles(client, user_db_populated):
    util.pp(user_db_populated.get_profile('PASTA-61b8b8872c13469faf4a44e3ff50b848'))
    response = client.get('/v1/profile/list')
    assert response.status_code == starlette.status.HTTP_200_OK
    sample.assert_equal_json(response.text, 'list_profiles.json')


# @pytest.mark.skip
def test_map_identity(client, user_db_populated):
    token_a = tests.util.create_test_pasta_token(
        'PASTA-e851e1a4b19c4b78992455807fe79534', user_db_populated
    )
    token_b = tests.util.create_test_pasta_token(
        'PASTA-61b8b8872c13469faf4a44e3ff50b848', user_db_populated
    )
    response = client.post(
        '/v1/profile/map', params={'token_src_str': token_a, 'token_dst_str': token_b}
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    db_json = tests.util.get_db_as_json(user_db_populated)
    sample.assert_equal_json(db_json, 'map_identity.json')


def test_get_profile(client, user_db_populated):
    token = tests.util.create_test_pasta_token(
        'PASTA-61b8b8872c13469faf4a44e3ff50b848', user_db_populated
    )
    response = client.get('/v1/profile/get', params={'token_str': token})
    assert response.status_code == starlette.status.HTTP_200_OK
    sample.assert_equal_json(response.text, 'get_profile.json')


def test_profile_disable(client, user_db_populated):
    token = tests.util.create_test_pasta_token(
        'PASTA-61b8b8872c13469faf4a44e3ff50b848', user_db_populated
    )
    response = client.post('/v1/profile/disable', params={'token_str': token})
    assert response.status_code == starlette.status.HTTP_200_OK
    db_json = tests.util.get_db_as_json(user_db_populated)
    sample.assert_equal_json(db_json, 'profile_disable.json')


def test_identity_drop(client, user_db_populated):
    token = tests.util.create_test_pasta_token(
        'PASTA-c422bd31545b4d7080a84ef1ba4a6a67', user_db_populated
    )
    response = client.post(
        '/v1/identity/drop',
        params={
            'token_str': token,
            'idp_name': 'github',
            'uid': 'https://github.com/testuser',
        },
    )
    assert response.status_code == starlette.status.HTTP_200_OK
    db_json = tests.util.get_db_as_json(user_db_populated)
    sample.assert_equal_json(db_json, 'profile_drop.json')


def test_identity_list(client, user_db_populated):
    token = tests.util.create_test_pasta_token(
        'PASTA-61b8b8872c13469faf4a44e3ff50b848', user_db_populated
    )
    response = client.get('/v1/identity/list', params={'token_str': token})
    assert response.status_code == starlette.status.HTTP_200_OK
    sample.assert_equal_json(response.text, 'identity_list.json')
