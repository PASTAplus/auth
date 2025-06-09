import daiquiri
import fastapi
import starlette.datastructures
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.models.identity
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


@router.get('/ui/avatar')
async def get_ui_avatar(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    avatar_list = [
        {
            'url': util.avatar.get_initials_avatar_url(token_profile_row.initials),
            'idp_name': None,
            'idp_uid': '',
        }
    ]
    for identity_row in token_profile_row.identities:
        if identity_row.has_avatar:
            avatar_list.append(
                {
                    'url': util.avatar.get_identity_avatar_url(identity_row),
                    'idp_name': identity_row.idp_name.name,
                    'idp_uid': identity_row.idp_uid,
                }
            )

    return util.template.templates.TemplateResponse(
        'avatar.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            'profile': token_profile_row,
            'resource_type_list': await dbi.get_resource_types(token_profile_row),
            # Page
            'request': request,
            'avatar_list': avatar_list,
        },
    )


#
# Internal routes
#


@router.post('/avatar/update')
async def post_avatar_update(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    idp_name_str = form_data.get('idp_name')
    idp_uid = form_data.get('idp_uid')

    log.info(f'Updating avatar: idp_name_str={idp_name_str}, idp_uid={idp_uid}')

    idp_name = db.models.identity.IdpName[idp_name_str]

    if idp_uid == '':
        token_profile_row.has_avatar = False
        avatar_path = util.avatar.get_avatar_path('profile', token_profile_row.edi_id)
        avatar_path.unlink(missing_ok=True)
    else:
        token_profile_row.has_avatar = True
        avatar_img = util.avatar.get_avatar_path(idp_name.name.lower(), idp_uid).read_bytes()
        util.avatar.save_avatar(avatar_img, 'profile', token_profile_row.edi_id)

    await dbi.update_profile(token_profile_row, has_avatar=idp_uid != '')

    return util.redirect.internal('/ui/profile', refresh='true')


@router.get('/avatar/gen/{initials}')
async def get_avatar_gen(
    initials: str,
):
    """Return an avatar image with the given initials."""
    return starlette.responses.Response(
        content=util.avatar.get_initials_avatar_path(initials).read_bytes(),
        media_type='image/png',
    )
