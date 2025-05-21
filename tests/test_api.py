import sample
import tests.util
import starlette.status
import util.pretty


import db.profile
import sample
import tests.utils
import db.resource_tree
import db.permission


# @pytest.mark.skip
def test_list_profiles(client, user_db_populated):
    util.pretty.pp(user_db_populated.get_profile('EDI-61b8b8872c13469faf4a44e3ff50b848'))
    response = client.get('/v1/profile/list')
    assert response.status_code == starlette.status.HTTP_200_OK
    sample.assert_equal_json(response.text, 'list_profiles.json')


@pytest.mark.skip
@pytest.mark.asyncio
async def test_pop_session(pop_session):
    s = pop_session
    edi_id_list = [
        p.edi_id for p in (await s.execute(sqlalchemy.select(db.profile.Profile))).scalars().all()
    ]
    assert len(edi_id_list) > 10


def test_get_profile(client, user_db_populated):
    token = tests.util.create_test_pasta_token(
        'EDI-61b8b8872c13469faf4a44e3ff50b848', user_db_populated
    )
    response = client.get('/v1/profile/get', params={'token_str': token})
    assert response.status_code == starlette.status.HTTP_200_OK
    sample.assert_equal_json(response.text, 'get_profile.json')


@pytest.mark.skip
@pytest.mark.asyncio
async def test_list_profiles2(client, pop_session):
    """Test the /v1/profile/list endpoint."""
    result = (await pop_session.execute(sqlalchemy.select(db.profile.Profile))).scalars().all()
    print([p.edi_id for p in result])


# @pytest.mark.skip
@pytest.mark.asyncio
async def test_3(client, pop_udb, profile_row):
#     rows = (await pop_udb.session.execute(sqlalchemy.select(db.permission.Rule))).scalars().all()
#     for row in rows:
#         print('-' * 80)
#         print(row)
#         print(row.id)
#         print(row.permission)

    resource_query = await pop_udb.get_resource_list(profile_row, '', None)
    resource_tree = db.resource_tree.get_resource_tree_for_ui(resource_query)
    # pprint.pp(resource_tree)
    print(json.dumps(resource_tree, indent=2))

def test_identity_list(client, user_db_populated):
    token = tests.util.create_test_pasta_token(
        'EDI-61b8b8872c13469faf4a44e3ff50b848', user_db_populated
    )
    response = client.get('/v1/identity/list', params={'token_str': token})
    assert response.status_code == starlette.status.HTTP_200_OK
    sample.assert_equal_json(response.text, 'identity_list.json')
