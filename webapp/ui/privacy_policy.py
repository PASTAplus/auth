import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import db.iface
import util.avatar
import util.filesystem
import util.old_token
import util.pasta_crypto
import util.pasta_jwt
import util.pasta_ldap
import util.search_cache
import util.template
import util.utils

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

# Internal routes


@router.post('/policy/accept')
async def policy_accept(
    request: starlette.requests.Request,
    udb: db.iface.UserDb = fastapi.Depends(db.iface.udb),
    token: util.pasta_jwt.PastaJwt | None = fastapi.Depends(util.pasta_jwt.token),
):
    form = await request.form()
    is_accepted = form.get('action') == 'accept'

    if not is_accepted:
        return util.utils.redirect_internal(
            '/signout', error='Login unsuccessful: Privacy policy not accepted'
        )

    udb.set_privacy_policy_accepted(token.pasta_id)
    return util.utils.redirect_internal('/ui/profile')
