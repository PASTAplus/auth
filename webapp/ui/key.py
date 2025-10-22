import datetime

import daiquiri
import fastapi
import starlette.datastructures
import starlette.exceptions
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import util.avatar
import util.dependency
import util.edi_token
import util.url
import util.template

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

#
# UI routes
#


# The date format required by the HTML5 datepicker.
DATE_FORMAT = '%Y-%m-%d'

@router.get('/ui/key')
async def get_ui_token(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    # We create a new EdiTokenClaims here, in order to pick up any changes that have been made to
    # the profile since the last login.
    now_dt = datetime.datetime.now()
    key_list = [
        {
            'id': k.id,
            'key_id': k.key_id,
            'description': k.description,
            'valid_from': k.valid_from.strftime(DATE_FORMAT),
            'valid_to': k.valid_to.strftime(DATE_FORMAT),
            'created': k.created.strftime(DATE_FORMAT),
            'updated': k.updated.strftime(DATE_FORMAT),
            'duration': format_exact_duration(k.valid_from, k.valid_to),
            'last_used': k.updated.strftime(DATE_FORMAT) if k.last_used else None,
            'use_count': k.use_count,
            'active': k.valid_from <= now_dt <= k.valid_to,
        }
        for k in await dbi.get_keys(token_profile_row)
    ]
    group_list = [
        {
            'id': g.id,
            'edi_id': g.edi_id,
            'name': g.name,
            'description': g.description,
        }
        for g in await dbi.get_all_owned_groups(token_profile_row)
    ]
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
            'key_list': key_list,
            'group_list': group_list,
            'now': now_dt.strftime(DATE_FORMAT),
            'now_plus_one_year': (now_dt + datetime.timedelta(days=365)).strftime(
                DATE_FORMAT
            ),
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
    description_str = form_data.get('key-description')
    from_dt = datetime.datetime.strptime(form_data.get('key-valid-from'), '%Y-%m-%d')
    to_dt = datetime.datetime.strptime(form_data.get('key-valid-to'), '%Y-%m-%d')
    await dbi.create_key(token_profile_row, description_str, from_dt, to_dt)
    return util.url.internal('/ui/key', info='API key created successfully.')


@router.post('/ui/api/key/update')
async def post_api_key_update(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    key_id = form_data.get('key-id')
    description_str = form_data.get('key-description')
    from_dt = datetime.datetime.strptime(form_data.get('key-valid-from'), '%Y-%m-%d')
    to_dt = datetime.datetime.strptime(form_data.get('key-valid-to'), '%Y-%m-%d')
    await dbi.update_key(token_profile_row, key_id, description_str, from_dt, to_dt)
    return util.url.internal('/ui/key', info='API key updated successfully.')


@router.post('/ui/api/key/delete')
async def post_api_key_delete(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    await dbi.delete_key(token_profile_row, form_data.get('key-id'))
    return util.url.internal('/ui/key', info='API key deleted successfully.')


#
# Utils
#


def format_exact_duration(start_date, end_date):
    # Return the difference between two real dates in years, months and days.
    years = end_date.year - start_date.year
    months = end_date.month - start_date.month
    days = end_date.day - start_date.day
    if days < 0:
        months -= 1
        prev_month = (end_date.month - 1) or 12
        prev_year = end_date.year if end_date.month > 1 else end_date.year - 1
        last_month_day = (
            datetime.date(prev_year, prev_month + 1, 1) - datetime.date(prev_year, prev_month, 1)
        ).days
        days += last_month_day
    if months < 0:
        years -= 1
        months += 12

    parts = []
    if years > 0:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months > 0:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    return ', '.join(parts)
