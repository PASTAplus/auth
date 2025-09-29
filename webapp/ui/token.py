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
import util.redirect
import util.template

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

#
# UI routes
#


@router.get('/ui/token')
async def get_ui_token(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
    token: util.dependency.EdiTokenClaims | None = fastapi.Depends(util.dependency.token),
):
    return util.template.templates.TemplateResponse(
        'token.html',
        {
            # Base
            'request': request,
            'profile': token_profile_row,
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row),
            'error_msg': request.query_params.get('error'),
            'info_msg': request.query_params.get('info'),
            # Page
            'token_pp': await util.edi_token.claims_pformat(dbi, request.state.claims),
            'filename': f'token-{token.edi_id}.jwt',
            'lifetime': token.exp - token.iat // 3600,
        },
    )


#
# Internal routes
#


@router.get('/ui/api/token/download')
async def get_token_download(
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
    token: util.dependency.EdiTokenClaims | None = fastapi.Depends(util.dependency.token),
):
    x = await util.edi_token.create(dbi, token_profile_row)
    # claims_obj = await util.edi_token.create_claims(dbi, token_profile_row)
    response = starlette.responses.Response(
        content=x.encode(),
        media_type='application/octet-stream',
    )
    response.headers['Content-Disposition'] = f'attachment; filename="token-{token.edi_id}.jwt"'
    return response
