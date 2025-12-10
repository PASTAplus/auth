import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import db.models.profile
import util.avatar
import util.dependency
import util.edi_token
import util.url
import util.template
import util.url

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

#
# UI routes
#


@router.get('/ui/identity')
async def get_ui_identity(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    profile_list = [
        {
            'idp_name': token_profile_row.idp_name,
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row),
            'idp_logo_url': util.url.get_idp_logo_url(token_profile_row.idp_name),
            'email': token_profile_row.email,
            'common_name': token_profile_row.common_name,
            'edi_id': token_profile_row.edi_id,
            'sort_key': 0,
        }
    ]

    for linked_profile_row in await dbi.get_linked_profile_list(token_profile_row.id):
        profile_list.append(
            {
                'profile_id': linked_profile_row.id,
                'idp_name': linked_profile_row.idp_name,
                'avatar_url': await util.avatar.get_profile_avatar_url(dbi, linked_profile_row),
                'idp_logo_url': util.url.get_idp_logo_url(linked_profile_row.idp_name),
                'email': linked_profile_row.email,
                'common_name': linked_profile_row.common_name,
                'edi_id': linked_profile_row.edi_id,
                'sort_key': 1,
            }
        )

    profile_list.sort(
        key=lambda x: (x['sort_key'], x['idp_name'].name, x['email'], x['common_name'])
    )

    return util.template.templates.TemplateResponse(
        'identity.html',
        {
            # Base
            'request': request,
            'profile': token_profile_row,
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row),
            'error_msg': request.query_params.get('error'),
            'info_msg': request.query_params.get('info'),
            # Page
            'profile_list': profile_list,
        },
    )


#
# Internal routes
#


@router.post('/ui/api/profile/unlink')
async def post_profile_unlink(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    profile_id = int(form_data.get('unlink-profile-id'))
    await dbi.unlink_profile(token_profile_row, profile_id)
    return util.url.internal('/ui/identity', info='Profile unlinked successfully.')
