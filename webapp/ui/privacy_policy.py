import daiquiri
import fastapi
import starlette.responses
import starlette.requests
import starlette.templating

import pasta_crypto
import ui.forms
import user_db
import util
from config import Config

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()
templates = starlette.templating.Jinja2Templates(Config.HERE_PATH / 'templates')


@router.get('/auth/accept')
async def accept_get(request: starlette.requests.Request):
    """Require the user to accept the privacy policy.

    This only serves the form. The form submission is handled by accept_post().
    """
    uid = request.query_params.get('uid')
    target = request.query_params.get('target')

    log.debug(f'Privacy policy accept form (GET): uid="{uid}" target="{target}"')

    return templates.TemplateResponse(
        'accept.html',
        {
            'request': request,
            'target': request.query_params.get('target'),
            'pasta_token': request.query_params.get('pasta_token'),
            'full_name': request.query_params.get('full_name'),
            'email': request.query_params.get('email'),
            'uid': request.query_params.get('uid'),
            'idp_name': request.query_params.get('idp_name'),
            'idp_token': request.query_params.get('idp_token'),
        },
    )


@router.post('/auth/accept')
async def accept_post(
    request: starlette.requests.Request,
    udb: user_db.UserDb = fastapi.Depends(user_db.udb),
):
    """Require the user to accept the privacy policy.

    If the policy is accepted, redirect back to the target with a new token.
    If the policy is not accepted, redirect back to the target with an error.
    """
    form = await request.form()
    uid = form.get('uid')
    target = form.get('target')
    is_accepted = form.get('action') == 'accept'

    log.debug(f'Privacy policy accept form (POST): uid="{uid}" target="{target}"')

    if not is_accepted:
        log.warn(f'Privacy policy not accepted: uid="{uid}" target="{target}"')
        return util.redirect(
            target,
            error='Login unsuccessful: Privacy policy not accepted',
        )

    udb.set_privacy_policy_accepted(
        udb.get_identity(form.get('idp_name'), uid=uid).profile.urid
    )

    log.debug(f'Privacy policy accepted: uid="{uid}" target="{target}"')

    return util.redirect_target(
        target=form.get('target'),
        pasta_token=form.get('pasta_token'),
        full_name=form.get('full_name'),
        email=form.get('email'),
        uid=form.get('uid'),
        idp_name=form.get('idp_name'),
        idp_token=form.get('idp_token'),
    )
