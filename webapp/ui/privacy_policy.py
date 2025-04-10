import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import util.dependency
import util.pasta_jwt
import util.redirect

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

#
# Internal routes
#


@router.post('/policy/accept')
async def policy_accept(
    request: starlette.requests.Request,
    udb: util.dependency.UserDb = fastapi.Depends(util.dependency.udb),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form = await request.form()
    is_accepted = form.get('action') == 'accept'

    if not is_accepted:
        return util.redirect.internal(
            '/signout', error='Login unsuccessful: Privacy policy not accepted'
        )

    await udb.set_privacy_policy_accepted(token_profile_row)
    return util.redirect.internal('/ui/profile')
