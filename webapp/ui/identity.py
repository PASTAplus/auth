import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import db.models.identity
import util.avatar
import util.dependency
import util.edi_token
import util.redirect
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
    token: util.dependency.EdiTokenClaims | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    identity_list = []
    for identity_row in token_profile_row.identities:
        identity_list.append(
            {
                'idp_name': identity_row.idp_name,
                'idp_uid': identity_row.idp_uid,
                'avatar_url': util.avatar.get_identity_avatar_url(identity_row),
                'idp_logo_url': util.url.get_idp_logo_url(identity_row.idp_name),
                'common_name': identity_row.email,
            }
        )

    identity_list.sort(key=lambda x: (x['idp_name'].name, x['common_name']))

    return util.template.templates.TemplateResponse(
        'identity.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            'profile': token_profile_row,
            # Page
            'request': request,
            'identity_list': identity_list,
            'error_msg': request.query_params.get('error_msg'),
            'success_msg': request.query_params.get('success_msg'),
        },
    )


#
# Internal routes
#


@router.post('/ui/api/identity/unlink')
async def post_identity_unlink(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    idp_name_str = form_data.get('idp_name')
    idp_uid = form_data.get('idp_uid')

    log.info(f'Unlinking identity: idp_name_str={idp_name_str}, idp_uid={idp_uid}')

    await dbi.delete_identity(token_profile_row, db.models.identity.IdpName[idp_name_str], idp_uid)

    return util.redirect.internal('/ui/identity', success_msg='Account unlinked successfully.')
