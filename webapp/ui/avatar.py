import daiquiri
import fastapi
import starlette.datastructures
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.models.profile
import util.avatar
import util.dependency
import util.edi_token
import util.redirect
import util.template

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

#
# UI routes
#


@router.get('/ui/avatar')
async def get_ui_avatar(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    avatar_list = [
        {
            'url': util.avatar.get_initials_avatar_url(
                util.avatar.get_profile_initials(token_profile_row)
            ),
            'profile_id': 0,
        }
    ]
    if token_profile_row.avatar_ver:
        avatar_list.append(
            {
                'url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row),
                'profile_id': token_profile_row.id,
            }
        )
    for linked_profile_row in await dbi.get_linked_profile_list(token_profile_row.id):
        if linked_profile_row.avatar_ver:
            avatar_list.append(
                {
                    'url': await util.avatar.get_profile_avatar_url(dbi, linked_profile_row),
                    'profile_id': linked_profile_row.id,
                }
            )
    return util.template.templates.TemplateResponse(
        'avatar.html',
        {
            # Base
            'request': request,
            'profile': token_profile_row,
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row),
            'error_msg': request.query_params.get('error'),
            'success_msg': request.query_params.get('success'),
            # Page
            'avatar_list': avatar_list,
        },
    )


#
# Internal API routes
#


@router.post('/ui/api/avatar/update')
async def post_avatar_update(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    profile_id = int(form_data.get('profile_id'))
    if profile_id == 0:
        profile_id = None
    await dbi.update_profile(token_profile_row, avatar_profile_id=profile_id)
    return util.redirect.internal('/ui/profile', success='Avatar updated successfully.')


@router.get('/ui/api/avatar/gen/{initials}')
async def get_avatar_gen(
    initials: str,
):
    """Return an avatar image with the given initials."""
    return starlette.responses.Response(
        content=util.avatar.get_initials_avatar_path(initials).read_bytes(),
        media_type='image/png',
    )
