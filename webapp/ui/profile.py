import daiquiri
import fastapi
import starlette.datastructures
import starlette.requests
import starlette.responses
import starlette.status
import starlette.templating

import db.iface
import jwt_token
import util
from config import Config

log = daiquiri.getLogger(__name__)


router = fastapi.APIRouter()
templates = starlette.templating.Jinja2Templates(Config.TEMPLATES_PATH)


# We allow opening the profile via POST in addition to GET, to be compliant with what
# other clients except. This comes into effect when redirected through the privacy
# policy.
@router.api_route('/profile', methods=['GET', 'POST'])
async def profile(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: jwt_token.NewToken | None = fastapi.Depends(jwt_token.token),
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


@router.post('/profile/update')
async def profile_update(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: jwt_token.NewToken | None = fastapi.Depends(jwt_token.token),
):
    profile_dict = await request.json()
    log.info(profile_dict)
    udb.update_profile(token.urid, **profile_dict)


@router.get('/avatar')
async def avatar(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: jwt_token.NewToken | None = fastapi.Depends(jwt_token.token),
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

    return templates.TemplateResponse(
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


@router.post('/avatar/update')
async def avatar_update(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: jwt_token.NewToken | None = fastapi.Depends(jwt_token.token),
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
        starlette.datastructures.URL('/profile').include_query_params(refresh='true'),
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
