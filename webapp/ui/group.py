import daiquiri
import fastapi
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.iface
import util.avatar
import util.dependency
import util.pasta_jwt
import util.redirect
import util.search_cache
import util.template

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

# UI routes


@router.get('/ui/group')
async def get_ui_group(
    request: starlette.requests.Request,
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
):
    profile_row = udb.get_profile(token.pasta_id)

    group_list = []

    for group_row in profile_row.groups:
        group_list.append(
            {
                'id': group_row.id,
                'pasta_id': group_row.pasta_id,
                'name': group_row.name,
                'description': group_row.description,
                'member_count': group_row.member_count,
                'updated': group_row.updated,
            }
        )

    # TODO: Create a toggle for these sorts?
    # group_list.sort(key=lambda x: x['name'])
    group_list.sort(key=lambda x: x['updated'])

    return util.template.templates.TemplateResponse(
        'group.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            'profile': token_profile_row,
            'resource_type_list': await udb.get_resource_types(token_profile_row),
            # Page
            'request': request,
            'group_list': group_list,
        },
    )


@router.get('/ui/group/member/{group_id}')
async def get_ui_group_member(
    group_id: str,
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    # form_data = await request.form()
    # form_data.get('group-id')
    profile_row = udb.get_profile(token.pasta_id)
    group_row = udb.get_group(profile_row, int(group_id))
    # group_row.created = group_row.created.strftime('%Y-%m-%d %H:%M')
    # group_row.updated = group_row.updated.strftime('%Y-%m-%d %H:%M')
    group_row.created = group_row.created.strftime('%m/%d/%Y %I:%M %p')
    group_row.updated = group_row.updated.strftime('%m/%d/%Y %I:%M %p')
    return util.template.templates.TemplateResponse(
        'member.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            'profile': token_profile_row,
            'resource_type_list': await udb.get_resource_types(token_profile_row),
            # Page
            'request': request,
            'group_row': group_row,
        },
    )


# Internal routes


@router.post('/group/new')
async def post_group_new(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    name = form_data.get('name')
    description = form_data.get('description')
    await udb.create_group(token_profile_row, name, description)
    return util.redirect.internal('/ui/group')


@router.post('/group/edit')
async def post_group_edit(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    group_id = form_data.get('group-id')
    name = form_data.get('name')
    description = form_data.get('description')
    await udb.update_group(token_profile_row, group_id, name, description)
    return util.redirect.internal('/ui/group')


@router.post('/group/delete')
async def post_group_delete(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    group_id = form_data.get('group-id')
    await udb.delete_group(token_profile_row, group_id)
    return util.redirect.internal('/ui/group')


@router.get('/group/member/list/{group_id}')
async def post_group_member_list(
    group_id: str,
    # request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    profile_row = udb.get_profile(token.pasta_id)
    group_row = udb.get_group(profile_row, int(group_id))
    member_list = udb.get_group_member_list(profile_row, group_row.id)
    member_list = sorted(member_list, key=lambda x: x.profile.full_name)
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'member_list': await get_client_profile_list(
                [m.profile for m in member_list]
            ),
        }
    )


@router.post('/group/member/search')
async def post_group_member_search(
    request: starlette.requests.Request,
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    query_dict = await request.json()
    # profile_row = udb.get_profile(token.pasta_id)
    # group_row = udb.get_group(profile_row, form_data.get('group-id'))
    query_str = query_dict.get('query')
    principal_list = await util.search_cache.search(query_str, include_groups=False)
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'candidate_list': await get_client_profile_list(candidate_list),
        }
    )


async def get_client_profile_list(profile_list):
    """Create a set of plain key/value dicts with limited profile values for exposing
    client side."""
    return [
        {
            'profile_id': p.id,
            'full_name': p.full_name,
            'email': p.email,
            'organization': p.organization,
            'association': p.association,
            'avatar_url': p.avatar_url,
        }
        for p in profile_list
    ]


@router.post('/group/member/add-remove')
async def post_group_member_add_remove(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    request_dict = await request.json()
    profile_row = udb.get_profile(token.pasta_id)
    is_add = request_dict['is_add']
    group_row = udb.get_group(profile_row, request_dict['group_id'])
    f = udb.add_group_member if is_add else udb.delete_group_member
    f(profile_row, group_row.id, request_dict['member_profile_id'])
    return starlette.responses.JSONResponse({'status': 'ok'})
