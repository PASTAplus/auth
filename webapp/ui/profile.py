import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import db.iface
import pasta_jwt
import util
from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()
templates = starlette.templating.Jinja2Templates(Config.TEMPLATES_PATH)


# UI routes

# We allow opening the profile via POST in addition to GET, to be compliant with what
# other clients except. This comes into effect when redirected through the privacy
# policy.
@router.api_route('/ui/profile', methods=['GET', 'POST'])
async def profile(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    profile_row = udb.get_profile(token.urid)

    return templates.TemplateResponse(
        'profile.html',
        {
            # Base
            'token': token,
            'avatar_url': util.get_profile_avatar_url(
                profile_row,
                refresh=request.query_params.get('refresh') == 'true',
            ),
            #
            'request': request,
            'profile': profile_row,
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


