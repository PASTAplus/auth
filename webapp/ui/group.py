import daiquiri
import fastapi
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import util.avatar
import util.dependency
import util.edi_token
import util.redirect
import util.search_cache
import util.template

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

#
# UI routes
#


@router.get('/ui/group')
async def get_ui_group(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    group_list = []

    owned_groups = await dbi.get_all_owned_groups(token_profile_row)

    # for group_row in token_profile_row.groups:
    for group_row in owned_groups:
        group_list.append(
            {
                'id': group_row.id,
                'edi_id': group_row.edi_id,
                'name': group_row.name,
                'description': group_row.description,
                'member_count': await dbi.get_group_member_count(token_profile_row, group_row.id),
                'updated': group_row.updated,
            }
        )

    # TODO: Create a toggle for these sorts?
    # group_list.sort(key=lambda x: x['name'])
    group_list.sort(key=lambda x: x['updated'], reverse=True)

    return util.template.templates.TemplateResponse(
        'group.html',
        {
            # Base
            'profile': token_profile_row,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            # Page
            'request': request,
            'group_list': group_list,
        },
    )


@router.get('/ui/group/member/{group_id}')
async def get_ui_group_member(
    group_id: int,
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    group_row = await dbi.get_owned_group(token_profile_row, group_id)
    group_row.created = group_row.created.strftime('%m/%d/%Y %I:%M %p')
    group_row.updated = group_row.updated.strftime('%m/%d/%Y %I:%M %p')
    return util.template.templates.TemplateResponse(
        'member.html',
        {
            # Base
            'profile': token_profile_row,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            # Page
            'request': request,
            'group_row': group_row,
        },
    )


#
# Internal routes
#


@router.post('/ui/api/group/new')
async def post_group_new(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    name = form_data.get('name')
    description = form_data.get('description')
    await dbi.create_group(token_profile_row, name, description)
    return util.redirect.internal('/ui/group')


@router.post('/ui/api/group/edit')
async def post_group_edit(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    group_id = int(form_data.get('group-id'))
    name = form_data.get('name')
    description = form_data.get('description')
    await dbi.update_group(token_profile_row, group_id, name, description)
    return util.redirect.internal('/ui/group')


@router.post('/ui/api/group/delete')
async def post_group_delete(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    group_id = int(form_data.get('group-id'))
    await dbi.delete_group(token_profile_row, group_id)
    return util.redirect.internal('/ui/group')


@router.get('/ui/api/group/member/list/{group_id}')
async def get_group_member_list(
    group_id: int,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    group_row = await dbi.get_owned_group(token_profile_row, group_id)
    member_list = await dbi.get_group_member_list(token_profile_row, group_row.id)
    member_list.sort(
        # Sort members by common name, or by edi_id if common_name is None. We sort edi_id after
        # common name by prepending \uffff, a high unicode character, to the edi_id key.
        key=lambda x: x.profile.common_name
        or ('\uffff' + x.profile.edi_id)
    )
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'member_list': [
                {
                    'profile_id': p.id,
                    'edi_id': p.edi_id,
                    'title': p.common_name,
                    'description': p.email,
                    'avatar_url': p.avatar_url,
                }
                for p in [m.profile for m in member_list]
            ],
        }
    )


@router.post('/ui/api/group/member/search')
async def post_group_member_search(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    # Prevent this from being called by anyone not logged in
    if token_profile_row is None:
        return starlette.responses.JSONResponse(
            {'status': 'error', 'message': 'Not logged in'},
            status_code=starlette.status.HTTP_401_UNAUTHORIZED,
        )
    query_dict = await request.json()
    query_str = query_dict.get('query')
    principal_list = await util.search_cache.search(dbi, query_str, include_groups=False)
    return starlette.responses.JSONResponse(
        {
            'status': 'ok',
            'principal_list': principal_list,
        }
    )


@router.post('/ui/api/group/member/add-remove')
async def post_group_member_add_remove(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    request_dict = await request.json()
    is_add = request_dict['is_add']
    group_row = await dbi.get_owned_group(token_profile_row, int(request_dict['group_id']))
    f = dbi.add_group_member if is_add else dbi.delete_group_member
    # noinspection PyArgumentList
    await f(token_profile_row, group_row.id, int(request_dict['member_profile_id']))
    return starlette.responses.JSONResponse({'status': 'ok'})
