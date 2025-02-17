import daiquiri
import fastapi
import starlette.datastructures
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import util.avatar
import util.filesystem
import util.old_token
import util.pasta_crypto
import util.pasta_jwt
import util.pasta_ldap
import util.search_cache
import util.utils
import db.iface
import util.template

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

# UI routes


@router.get('/ui/avatar')
async def get_ui_avatar(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    profile_row = udb.get_profile(token.pasta_id)

    avatar_list = [
        {
            'url': util.avatar.get_initials_avatar_url(profile_row.initials),
            'idp_name': None,
            'idp_uid': '',
        }
    ]
    for identity_row in profile_row.identities:
        if identity_row.has_avatar:
            avatar_list.append(
                {
                    'url': util.avatar.get_identity_avatar_url(identity_row),
                    'idp_name': identity_row.idp_name,
                    'idp_uid': identity_row.idp_uid,
                }
            )

    return util.template.templates.TemplateResponse(
        'avatar.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(profile_row),
            'profile': profile_row,
            #
            'request': request,
            'avatar_list': avatar_list,
        },
    )


# Internal routes


@router.post('/avatar/update')
async def post_avatar_update(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    form_data = await request.form()
    idp_name = form_data.get('idp_name')
    idp_uid = form_data.get('idp_uid')

    log.info(f'Updating avatar: idp_name={idp_name}, idp_uid={idp_uid}')

    profile_row = udb.get_profile(token.pasta_id)

    if idp_uid == '':
        profile_row.has_avatar = False
        avatar_path = util.avatar.get_avatar_path('profile', profile_row.pasta_id)
        avatar_path.unlink(missing_ok=True)
    else:
        profile_row.has_avatar = True
        avatar_img = util.avatar.get_avatar_path(idp_name, idp_uid).read_bytes()
        util.avatar.save_avatar(avatar_img, 'profile', profile_row.pasta_id)

    udb.update_profile(token.pasta_id, has_avatar=idp_uid != '')

    return util.utils.redirect_internal('/ui/profile', refresh='true')


@router.get('/avatar/gen/{initials}')
async def get_avatar_gen(
    initials: str,
):
    """Return an avatar image with the given initials."""
    return starlette.responses.Response(
        content=util.avatar.get_initials_avatar_path(initials).read_bytes(),
        media_type='image/png',
    )
