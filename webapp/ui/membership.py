import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import util.avatar
import util.dependency
import util.pasta_jwt
import util.redirect
import util.template

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

#
# UI routes
#


@router.get('/ui/membership')
async def get_ui_membership(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    return util.template.templates.TemplateResponse(
        'membership.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(
                token_profile_row,
                refresh=request.query_params.get('refresh') == 'true',
            ),
            'profile': token_profile_row,
            'resource_type_list': await dbi.get_resource_types(token_profile_row),
            # Page
            'request': request,
            'group_membership_list': await dbi.get_group_membership_list(token_profile_row),
            'group_avatar': util.avatar.get_group_avatar_url(),
        },
    )


#
# Internal routes
#


@router.post('/membership/leave')
async def post_membership_leave(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    group_id = int(form_data.get('group-id'))
    await dbi.leave_group_membership(token_profile_row, group_id)
    return util.redirect.internal('/ui/membership')
