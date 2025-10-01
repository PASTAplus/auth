import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import util.avatar
import util.dependency
import util.edi_token
import util.redirect
import util.template

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter(prefix='/ui')

#
# UI routes
#


@router.get('/help')
async def get_ui_help(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    return util.template.templates.TemplateResponse(
        'help.html',
        {
            # Base
            'request': request,
            'profile': token_profile_row,
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row)
            if token_profile_row
            else None,
            'error_msg': request.query_params.get('error'),
            'info_msg': request.query_params.get('info'),
        },
    )
