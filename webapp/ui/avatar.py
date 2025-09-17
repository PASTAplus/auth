import daiquiri
import fastapi
import starlette.datastructures
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.models.profile
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


@router.get('/ui/avatar')
async def get_ui_avatar(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    avatar_list = [
        {
            'url': util.avatar.get_initials_avatar_url(token_profile_row.initials),
            'profile_id': token_profile_row.id,
        }
    ]
    if token_profile_row.avatar_ver:
        avatar_list.append(
            {
                'url': util.avatar.get_profile_avatar_url(token_profile_row),
                'profile_id': token_profile_row.id,
            }
        )
    for linked_profile_row in await dbi.get_linked_profiles(token_profile_row.id):
        if linked_profile_row.avatar_ver:
            avatar_list.append(
                {
                    'url': util.avatar.get_profile_avatar_url(linked_profile_row),
                    'profile_id': linked_profile_row.id,
                }
            )
    return util.template.templates.TemplateResponse(
        'avatar.html',
        {
            # Base
            'avatar_url': util.avatar.get_profile_avatar_url(token_profile_row),
            'profile': token_profile_row,
            # Page
            'request': request,
            'avatar_list': avatar_list,
        },
    )


#
# Internal API routes
#


@router.post('/ui/api/avatar/update')
async def post_avatar_update(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    idp_name_str = form_data.get('idp_name')
    idp_uid = form_data.get('idp_uid')

    log.info(f'Updating avatar: idp_name_str={idp_name_str}, idp_uid={idp_uid}')

    if idp_uid == '':
        token_profile_row.has_avatar = False
        avatar_path = util.avatar.get_avatar_path('profile', token_profile_row.edi_id)
        avatar_path.unlink(missing_ok=True)
    else:
        token_profile_row.has_avatar = True
        idp_name = db.models.profile.IdpName[idp_name_str]
        avatar_img = util.avatar.get_avatar_path(idp_name.name.lower(), idp_uid).read_bytes()
        util.avatar.save_avatar(avatar_img, 'profile', token_profile_row.edi_id)

    await dbi.update_profile(token_profile_row, has_avatar=idp_uid != '')

    return util.redirect.internal('/ui/profile', refresh='true')


@router.get('/ui/api/avatar/gen/{initials}')
async def get_avatar_gen(
    initials: str,
):
    """Return an avatar image with the given initials."""
    return starlette.responses.Response(
        content=util.avatar.get_initials_avatar_path(initials).read_bytes(),
        media_type='image/png',
    )
