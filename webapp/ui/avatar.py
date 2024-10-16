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

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()

# UI routes

@router.get('/ui/avatar')
async def avatar(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    profile_row = udb.get_profile(token.urid)

    avatar_list = [
        {
            'url': util.get_initials_avatar_url(profile_row.initials),
            'idp_name': None,
            'uid': '',
        }
    ]
    for identity_row in profile_row.identities:
        if identity_row.has_avatar:
            avatar_list.append(
                {
                    'url': util.get_identity_avatar_url(identity_row),
                    'idp_name': identity_row.idp_name,
                    'uid': identity_row.uid,
                }
            )

    return util.templates.TemplateResponse(
        'avatar.html',
        {
            # Base
            'token': token,
            'avatar_url': util.get_profile_avatar_url(profile_row),
            #
            'request': request,
            'avatar_list': avatar_list,
        },
    )

# Internal routes

@router.post('/avatar/update')
async def avatar_update(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    form_data = await request.form()
    idp_name = form_data.get('idp_name')
    uid = form_data.get('uid')

    log.info(f'Updating avatar: idp_name={idp_name}, uid={uid}')

    profile_row = udb.get_profile(token.urid)

    if uid == '':
        profile_row.has_avatar = False
        avatar_path = util.get_avatar_path('profile', profile_row.urid)
        avatar_path.unlink(missing_ok=True)
    else:
        profile_row.has_avatar = True
        avatar_img = util.get_avatar_path(idp_name, uid).read_bytes()
        util.save_avatar(avatar_img, 'profile', profile_row.urid)

    udb.update_profile(token.urid, has_avatar=uid != '')

    return starlette.responses.RedirectResponse(
        util.url('/ui/profile', refresh='true'),
        status_code=starlette.status.HTTP_303_SEE_OTHER,
    )


@router.get('/avatar/gen/{initials}')
async def avatar_gen(
    initials: str,
):
    """Return an avatar image with the given initials."""
    return starlette.responses.Response(
        content=util.get_initials_avatar_path(initials).read_bytes(),
        media_type='image/png',
    )
