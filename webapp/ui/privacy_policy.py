import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import util.dependency
import util.edi_token
import util.url

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()

#
# Internal routes
#


@router.post('/ui/api/policy/accept')
async def policy_accept(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    form = await request.form()
    is_accepted = form.get('action') == 'accept'

    if not is_accepted:
        return util.url.internal(
            '/signout', error='Login unsuccessful: Privacy policy not accepted'
        )

    await dbi.set_privacy_policy_accepted(token_profile_row)
    return util.url.internal(
        '/ui/profile', info=form.get('info-msg'), error=form.get('error-msg')
    )
