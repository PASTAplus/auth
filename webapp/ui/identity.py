import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import db.iface
import pasta_jwt
import util

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

# UI routes


@router.get('/ui/identity')
async def identity(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    profile_row = udb.get_profile(token.urid)

    identity_list = []
    for identity_row in profile_row.identities:
        identity_list.append(
            {
                'idp_name': identity_row.idp_name,
                'uid': identity_row.uid,
                'avatar_url': util.get_identity_avatar_url(identity_row),
                'idp_logo_url': util.get_idp_logo_url(identity_row.idp_name),
                'full_name': identity_row.email,
            }
        )

    identity_list.sort(key=lambda x: (x['idp_name'], x['full_name']))

    return util.templates.TemplateResponse(
        'identity.html',
        {
            # Base
            'token': token,
            'avatar_url': util.get_profile_avatar_url(profile_row),
            'profile': profile_row,
            #
            'request': request,
            'identity_list': identity_list,
        },
    )


# Internal routes


@router.post('/identity/unlink')
async def identity_unlink(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    profile_row = udb.get_profile(token.urid)

    form_data = await request.form()
    idp_name = form_data.get('idp_name')
    uid = form_data.get('uid')

    log.info(f'Unlinking identity: idp_name={idp_name}, uid={uid}')

    udb.delete_identity(profile_row, idp_name, uid)

    return util.redirect_internal('/ui/identity')
