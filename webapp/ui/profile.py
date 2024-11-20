import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import db.iface
import fuzz
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


# Internal routes


@router.post('/profile/update')
async def profile_update(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    profile_dict = await request.json()
    log.info(profile_dict)
    udb.update_profile(token.urid, **profile_dict)
    profile_row = udb.get_profile(token.urid)
    await fuzz.update(profile_row)


@router.post('/profile/delete')
async def profile_delete(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    udb.delete_profile(token.urid)
    return util.redirect_internal('/signout')
