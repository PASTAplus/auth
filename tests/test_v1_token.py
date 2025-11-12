"""Tests for v1/token endpoints."""

import pytest

import util.old_token
import util.edi_token
from config import Config

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(100),
]


async def test_token_refresh(anon_client, john_token):
    pasta_token = util.old_token.make_old_token(Config.TEST_USER_DN, Config.VETTED)
    response = anon_client.post(
        '/v1/token/refresh',
        json={
            'pasta-token': pasta_token,
            'edi-token': john_token,
        },
    )
    assert response.status_code == 200, response.text
    response_dict = response.json()
    assert 'pasta-token' in response_dict, response.text
    assert 'edi-token' in response_dict, response.text


# async def test_get_token_by_key(anon_client, john_token):
#     edi_token = util.edi_token.decode_edi_token(john_token)
#     token_key = edi_token['token_key']
#     response = anon_client.get(f'/v1/token/{token_key}')
#     assert response.status_code == 200, response.text
#     response_dict = response.json()
#     assert response_dict['token_key'] == token_key, response.text
