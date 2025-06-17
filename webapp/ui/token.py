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
import util.pasta_jwt
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
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
):
    return util.template.templates.TemplateResponse(
        'token.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            'profile': token_profile_row,
            'resource_type_list': await dbi.get_resource_types(token_profile_row),
            # Page
            'request': request,
            'token_pp': token.claims_pp,
            'filename': f'token-{token.edi_id}.jwt',
            'lifetime': (token.claims.get('exp') - token.claims.get('iat')) // 3600,
        },
    )


#
# Internal routes
#


@router.get('/token/download')
async def get_token_download(
    # request: starlette.requests.Request,
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    # token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
):
    if token is None:
        raise starlette.exceptions.HTTPException(
            status_code=starlette.status.HTTP_403_FORBIDDEN, detail='No token provided'
        )
    identity_row = await dbi.get_identity_by_id(token.claims.get('identityId'))
    response = starlette.responses.Response(
        content=(await util.pasta_jwt.make_jwt(dbi, identity_row)).encode(),
        media_type='application/octet-stream',
    )
    response.headers['Content-Disposition'] = f'attachment; filename="token-{token.edi_id}.jwt"'
    return response
