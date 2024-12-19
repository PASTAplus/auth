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

# We allow opening the profile via POST in addition to GET, to be compliant with what
# other clients except. TODO: Still needed?
@router.api_route('/ui/profile', methods=['GET', 'POST'])
async def profile(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    profile_row = udb.get_profile(token.urid)

    return util.templates.TemplateResponse(
        'profile.html',
        {
            # Base
            'token': token,
            'avatar_url': util.get_profile_avatar_url(
                profile_row,
                refresh=request.query_params.get('refresh') == 'true',
            ),
            'profile': profile_row,
            #
            'request': request,
        },
    )


@router.get('/ui/profile/edit')
async def profile_edit(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    profile_row = udb.get_profile(token.urid)

    return util.templates.TemplateResponse(
        'profile-edit.html',
        {
            # Base
            'token': token,
            'avatar_url': util.get_profile_avatar_url(
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
async def profile_edit_update(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    form_data = await request.form()
    util.log_dict(log.info, 'Updating profile', dict(form_data))
    udb.update_profile(
        token.urid,
        full_name=form_data.get('full-name'),
        email=form_data.get('email'),
        email_notifications='email-notifications' in form_data,
        organization=form_data.get('organization'),
        association=form_data.get('association'),
    )
    return util.redirect_internal('/ui/profile/edit', msg='Profile updated')


@router.post('/profile/edit/delete')
async def profile_edit_delete(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    udb.delete_profile(token.urid)
    return util.redirect_internal('/signout')
