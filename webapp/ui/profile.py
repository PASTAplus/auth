import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import util.avatar
import util.dependency
import util.edi_token
import util.pretty
import util.redirect
import util.template

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()


#
# UI routes
#


# We allow opening the profile via POST in addition to GET, to be compliant with what
# other clients except. TODO: Still needed?
@router.api_route('/ui/profile', methods=['GET', 'POST'])
async def get_post_ui_profile(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    return util.template.templates.TemplateResponse(
        'profile.html',
        {
            # Base
            'request': request,
            'profile': token_profile_row,
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row),
            'error_msg': request.query_params.get('error'),
            'success_msg': request.query_params.get('success'),
            # Page
        },
    )


@router.get('/ui/profile/edit')
async def get_ui_profile_edit(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    return util.template.templates.TemplateResponse(
        'profile-edit.html',
        {
            # Base
            'request': request,
            'profile': token_profile_row,
            'avatar_url': await util.avatar.get_profile_avatar_url(dbi, token_profile_row),
            'error_msg': request.query_params.get('error'),
            'success_msg': request.query_params.get('success'),
            # Page
        },
    )


#
# Internal routes
#


@router.post('/ui/api/profile/edit/update')
async def post_profile_edit_update(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form_data = await request.form()
    util.pretty.log_dict(log.info, 'Updating profile', dict(form_data))
    await dbi.update_profile(
        token_profile_row,
        common_name=form_data.get('common-name'),
        email=form_data.get('email'),
        email_notifications='email-notifications' in form_data,
    )
    return util.redirect.internal('/ui/profile/edit', success='Profile updated successfully.')


@router.post('/ui/api/profile/edit/delete')
async def post_profile_edit_delete(
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    await dbi.delete_profile(token_profile_row)
    return util.redirect.internal('/signout', success='Profile deleted successfully.')
