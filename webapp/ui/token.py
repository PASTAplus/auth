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
    identity_row = await dbi.get_profile_by_id(token.identityId)
    claims_obj = await util.edi_token.create_claims(dbi, identity_row)
    return util.template.templates.TemplateResponse(
        'token.html',
        {
            # Base
            'profile': token_profile_row,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            # Page
            'request': request,
            'token_pp': await util.edi_token.claims_pformat(dbi, claims_obj),
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
    token: util.dependency.EdiTokenClaims | None = fastapi.Depends(util.dependency.token),
):
    if token is None:
        raise starlette.exceptions.HTTPException(
            status_code=starlette.status.HTTP_403_FORBIDDEN, detail='No token provided'
        )
    identity_row = await dbi.get_profile_by_id(token.identityId)
    response = starlette.responses.Response(
        content=(await util.edi_token.create(dbi, identity_row)).encode(),
        media_type='application/octet-stream',
    )
    response.headers['Content-Disposition'] = f'attachment; filename="token-{token.edi_id}.jwt"'
    return response
