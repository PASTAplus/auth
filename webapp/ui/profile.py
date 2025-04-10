import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import db.iface
import util.avatar
import util.dependency
import util.pasta_jwt
import util.pretty
import util.template
import util.utils

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


# UI routes

# We allow opening the profile via POST in addition to GET, to be compliant with what
# other clients except. TODO: Still needed?
@router.api_route('/ui/profile', methods=['GET', 'POST'])
async def get_post_ui_profile(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    profile_row = udb.get_profile(token.pasta_id)

    return util.template.templates.TemplateResponse(
        'profile.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(
                profile_row,
                refresh=request.query_params.get('refresh') == 'true',
            ),
            'profile': profile_row,
            #
            'request': request,
        },
    )


@router.get('/ui/profile/edit')
async def get_ui_profile_edit(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token: util.dependency.PastaJwt | None = fastapi.Depends(util.dependency.token),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    profile_row = udb.get_profile(token.pasta_id)

    return util.template.templates.TemplateResponse(
        'profile-edit.html',
        {
            # Base
            'token': token,
            'avatar_url': util.avatar.get_profile_avatar_url(
                profile_row,
                refresh=request.query_params.get('refresh') == 'true',
            ),
            'profile': profile_row,
            #
            'request': request,
            'msg': request.query_params.get('msg'),
        },
    )


# Internal routes


@router.post('/profile/edit/update')
async def post_profile_edit_update(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    util.pretty.log_dict(log.info, 'Updating profile', dict(form_data))
    udb.update_profile(
        token.pasta_id,
        full_name=form_data.get('full-name'),
        email=form_data.get('email'),
        email_notifications='email-notifications' in form_data,
        organization=form_data.get('organization'),
        association=form_data.get('association'),
    )
    return util.utils.redirect_internal('/ui/profile/edit', msg='Profile updated')


@router.post('/profile/edit/delete')
async def post_profile_edit_delete(
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    udb.delete_profile(token.pasta_id)
    return util.utils.redirect_internal('/signout')
