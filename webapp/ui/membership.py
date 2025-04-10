import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import db.iface
import util.avatar
import util.dependency
import util.pasta_jwt
import util.template
import util.utils

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

# UI routes


@router.get('/ui/membership')
async def get_ui_membership(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    profile_row = udb.get_profile(token.pasta_id)
    return util.template.templates.TemplateResponse(
        'membership.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(
                profile_row,
                refresh=request.query_params.get('refresh') == 'true',
            ),
            'profile': profile_row,
            #
            'request': request,
            'group_membership_list': udb.get_group_membership_list(profile_row),
        },
    )


# Internal routes


@router.post('/membership/leave')
async def post_membership_leave(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    group_id = form_data.get('group-id')
    profile_row = udb.get_profile(token.pasta_id)
    udb.leave_group_membership(profile_row, group_id)
    return util.utils.redirect_internal('/ui/membership')
