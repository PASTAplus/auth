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


@router.get('/ui/identity')
async def get_ui_identity(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    profile_row = udb.get_profile(token.pasta_id)

    identity_list = []
    for identity_row in profile_row.identities:
        identity_list.append(
            {
                'idp_name': identity_row.idp_name,
                'idp_uid': identity_row.idp_uid,
                'avatar_url': util.avatar.get_identity_avatar_url(identity_row),
                'idp_logo_url': util.utils.get_idp_logo_url(identity_row.idp_name),
                'full_name': identity_row.email,
            }
        )

    identity_list.sort(key=lambda x: (x['idp_name'], x['full_name']))

    return util.template.templates.TemplateResponse(
        'identity.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(profile_row),
            'profile': profile_row,
            #
            'request': request,
            'identity_list': identity_list,
            'msg': request.query_params.get('msg'),
        },
    )


# Internal routes


@router.post('/identity/unlink')
async def post_identity_unlink(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    profile_row = udb.get_profile(token.pasta_id)

    form_data = await request.form()
    idp_name = form_data.get('idp_name')
    idp_uid = form_data.get('idp_uid')

    log.info(f'Unlinking identity: idp_name={idp_name}, idp_uid={idp_uid}')

    udb.delete_identity(profile_row, idp_name, idp_uid)

    return util.utils.redirect_internal('/ui/identity')
