import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import db.iface
import util.avatar
import util.filesystem
import util.old_token
import util.pasta_crypto
import util.pasta_jwt
import util.pasta_ldap
import util.search_cache
import util.template
import util.utils

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

# UI routes


@router.get('/ui/membership')
async def get_ui_membership(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
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
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    form_data = await request.form()
    group_id = form_data.get('group-id')
    profile_row = udb.get_profile(token.pasta_id)
    udb.leave_group_membership(profile_row, group_id)
    return util.utils.redirect_internal('/ui/membership')
