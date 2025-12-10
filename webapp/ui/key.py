import datetime

import daiquiri
import fastapi
import sqlalchemy.exc
import starlette.requests
import starlette.templating

import util.avatar
import util.date
import util.dependency
import util.edi_token
import util.template
import util.url

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

#
# UI routes
#


@router.get('/ui/key')
async def get_ui_key(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    # We create a new EdiTokenClaims here, in order to pick up any changes that have been made to
    # the profile since the last login.
    now_dt = datetime.datetime.now()
    try:
        year_dt = now_dt.replace(year=now_dt.year + 1)
    except ValueError:
        # Handle leap year (Feb 29 -> Feb 28)
        year_dt = now_dt.replace(year=now_dt.year + 1, month=2, day=28)
    year_dt -= datetime.timedelta(days=1)

    return util.template.templates.TemplateResponse(
        'key.html',
        {
            # Base
            'request': request,
            'profile': token_profile_row,
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row),
            'error_msg': request.query_params.get('error'),
            'info_msg': request.query_params.get('info'),
            # Page
            'key_list': [
                {
                    'id': k.id,
                    'name': k.name,
                    'group_id': k.group_id,
                    'secret_preview': k.secret_preview,
                    'valid_from': util.date.to_datepicker(k.valid_from),
                    'valid_to': util.date.to_datepicker(k.valid_to),
                    'created': util.date.to_datepicker(k.created),
                    'updated': util.date.to_datepicker(k.updated),
                    'last_used': util.date.to_datepicker(k.updated) if k.last_used else None,
                    'duration': util.date.format_duration(k.valid_from, k.valid_to),
                    'use_count': k.use_count,
                }
                for k in await dbi.get_key_list(token_profile_row)
            ],
            'group_list': [
                {
                    'id': g.id,
                    'edi_id': g.edi_id,
                    'name': g.name,
                    'description': g.description,
                }
                for g in await dbi.get_all_owned_groups(token_profile_row)
            ],
            'now': util.date.to_datepicker(now_dt),
            'now_plus_one_year': util.date.to_datepicker(year_dt),
            'new_secret': request.query_params.get('secret', ''),
        },
    )




#
# API routes
#


@router.post('/ui/api/key/new')
async def post_api_key_new(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    name_str = form_data.get('key-name')
    group_id = await _get_and_check_group_id(token_profile_row, dbi, form_data)
    from_dt = util.date.from_datepicker(form_data.get('key-valid-from'))
    to_dt = util.date.from_datepicker(form_data.get('key-valid-to'))
    secret_str = await dbi.create_key(token_profile_row, group_id, name_str, from_dt, to_dt)
    return util.url.internal('/ui/key', secret=secret_str)


@router.post('/ui/api/key/update')
async def post_api_key_update(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    key_id = int(form_data.get('key-id'))
    name_str = form_data.get('key-name')
    group_id = await _get_and_check_group_id(token_profile_row, dbi, form_data)
    from_dt = util.date.from_datepicker(form_data.get('key-valid-from'))
    to_dt = util.date.from_datepicker(form_data.get('key-valid-to'))
    await dbi.update_key(token_profile_row, key_id, group_id, name_str, from_dt, to_dt)
    return util.url.internal('/ui/key', info=f'API key "{name_str}" updated successfully.')


async def _get_and_check_group_id(token_profile_row, dbi, form_data) -> int | None:
    group_id = form_data.get('key-group-id')
    if group_id == 'profile':
        return None
    try:
        group_id = int(group_id)
    except (TypeError, ValueError):
        return None
    try:
        return (await dbi.get_owned_group(token_profile_row, group_id)).id
    except sqlalchemy.exc.NoResultFound:
        return None


@router.post('/ui/api/key/delete')
async def post_api_key_delete(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    await dbi.delete_key(token_profile_row, int(form_data.get('key-id')))
    return util.url.internal('/ui/key', info='API key deleted successfully.')
