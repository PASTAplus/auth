import uuid

import daiquiri
import fastapi
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating
import json

import db.group
import db.iface
import new_token
import util
from config import Config
import fuzz

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()
templates = starlette.templating.Jinja2Templates(Config.TEMPLATES_PATH)


@router.get('/group')
async def group(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: new_token.NewToken | None = fastapi.Depends(new_token.token),
):
    profile_row = udb.get_profile(token.urid)

    group_list = []

    for group_row in profile_row.groups:
        group_list.append(
            {
                'id': group_row.id,
                'grid': group_row.grid,
                'name': group_row.name,
                'description': group_row.description,
                'member_count': group_row.member_count,
                'updated': group_row.updated,
            }
        )

    # TODO: Create a toggle for these sorts?
    # group_list.sort(key=lambda x: x['name'])
    group_list.sort(key=lambda x: x['updated'])

    return templates.TemplateResponse(
        'group.html',
        {
            # Base
            'token': token,
            'avatar_url': util.get_profile_avatar_url(profile_row),
            #
            'request': request,
            'group_list': group_list,
        },
    )


@router.post('/group/new')
async def group_new(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: new_token.NewToken | None = fastapi.Depends(new_token.token),
):
    form_data = await request.form()
    name = form_data.get('name')
    description = form_data.get('description')
    profile_row = udb.get_profile(token.urid)
    udb.create_group(profile_row, name, description)
    return starlette.responses.RedirectResponse(
        Config.SERVICE_BASE_URL + '/group',
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )


@router.post('/group/edit')
async def group_edit(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: new_token.NewToken | None = fastapi.Depends(new_token.token),
):
    form_data = await request.form()
    group_id = form_data.get('group-id')
    name = form_data.get('name')
    description = form_data.get('description')
    profile_row = udb.get_profile(token.urid)
    udb.update_group(profile_row, group_id, name, description)
    return starlette.responses.RedirectResponse(
        Config.SERVICE_BASE_URL + '/group',
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )


@router.post('/group/delete')
async def group_delete(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: new_token.NewToken | None = fastapi.Depends(new_token.token),
):
    form_data = await request.form()
    group_id = form_data.get('group-id')
    profile_row = udb.get_profile(token.urid)
    udb.delete_group(profile_row, group_id)
    return starlette.responses.RedirectResponse(
        Config.SERVICE_BASE_URL + '/group',
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )


@router.get('/group/member/{group_id}')
async def group_member(
    group_id: str,
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: new_token.NewToken | None = fastapi.Depends(new_token.token),
):
    # form_data = await request.form()
    # form_data.get('group-id')
    profile_row = udb.get_profile(token.urid)
    group_row = udb.get_group(profile_row, int(group_id))
    # group_row.created = group_row.created.strftime('%Y-%m-%d %H:%M')
    # group_row.updated = group_row.updated.strftime('%Y-%m-%d %H:%M')
    group_row.created = group_row.created.strftime('%m/%d/%Y %I:%M %p')
    group_row.updated = group_row.updated.strftime('%m/%d/%Y %I:%M %p')
    member_list = udb.get_group_member_list(profile_row, group_row.id)
    member_list = sorted(member_list, key=lambda x: x.profile.full_name)
    return templates.TemplateResponse(
        'member.html',
        {
            # Base
            'token': token,
            'avatar_url': util.get_profile_avatar_url(profile_row),
            #
            'request': request,
            'group_row': group_row,
            'member_list': [m.profile for m in member_list],
        },
    )


@router.post('/group/member/search')
async def group_member_search(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    # Prevent this from being called by anyone not logged in
    _token: new_token.NewToken | None = fastapi.Depends(new_token.token),
):
    query_dict = await request.json()
    # profile_row = udb.get_profile(token.urid)
    # group_row = udb.get_group(profile_row, form_data.get('group-id'))

    query_str = query_dict.get('query')
    log.info(f'query_str: {query_str}')

    match_list = await fuzz.search(query_str)

    profile_list = udb.get_profiles_by_ids(match_list)

    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'candidate_list': [
                {
                    'profile_id': profile_row.id,
                    'full_name': profile_row.full_name,
                    'email': profile_row.email,
                    'organization': profile_row.organization,
                    'association': profile_row.association,
                    'avatar_url': str(profile_row.avatar_url),
                }
                for profile_row in profile_list
            ],
        }
    )


@router.post('/group/member/add-remove')
async def group_member_add_remove(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: new_token.NewToken | None = fastapi.Depends(new_token.token),
):
    request_dict = await request.json()
    profile_row = udb.get_profile(token.urid)
    is_add = request_dict['is_add']
    group_row = udb.get_group(profile_row, request_dict['group_id'])
    f = udb.add_group_member if is_add else udb.delete_group_member
    f(profile_row, group_row.id, request_dict['member_profile_id'])
    return starlette.responses.JSONResponse({'status': 'ok'})
