import daiquiri
import fastapi
import starlette.datastructures
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.iface
import pasta_jwt
import util
from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()
templates = starlette.templating.Jinja2Templates(Config.TEMPLATES_PATH)

# UI routes

@router.get('/ui/membership')
async def membership(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    profile_row = udb.get_profile(token.urid)
    return templates.TemplateResponse(
        'membership.html',
        {
            # Base
            'token': token,
            'avatar_url': util.get_profile_avatar_url(
                profile_row,
                refresh=request.query_params.get('refresh') == 'true',
            ),
            #
            'request': request,
            'group_membership_list': udb.get_group_membership_list(profile_row),
        },
    )

# Internal routes

@router.post('/membership/leave')
async def membership_leave(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    form_data = await request.form()
    group_id = form_data.get('group-id')
    profile_row = udb.get_profile(token.urid)
    udb.leave_group_membership(profile_row, group_id)
    return starlette.responses.RedirectResponse(
        starlette.datastructures.URL('/ui/membership'),
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )
