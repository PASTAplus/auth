import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import db.iface
import pasta_jwt
import util

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

# Internal routes


@router.post('/policy/accept')
async def policy_accept(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: pasta_jwt.PastaJwt | None = fastapi.Depends(pasta_jwt.token),
):
    form = await request.form()
    is_accepted = form.get('action') == 'accept'

    if not is_accepted:
        return util.redirect_internal(
            '/signout', error='Login unsuccessful: Privacy policy not accepted'
        )

    udb.set_privacy_policy_accepted(token.pasta_id)
    return util.redirect_internal('/ui/profile')
