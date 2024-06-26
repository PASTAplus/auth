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
def accept_get(request: starlette.requests.Request):
    """Require the user to accept the privacy policy.

    This only serves the form. The form submission is handled by accept_post().
    """
    uid = request.query_params.get('uid')
    target = request.query_params.get('target')

    log.debug(f'Privacy policy accept form (GET): uid="{uid}" target="{target}"')

    udb = user_db.UserDb()

    if udb.get_user(uid) is None:
        return f'Unknown uid: {uid}', 400

    return templates.TemplateResponse(
        'accept.html',
        {
            'form': ui.forms.AcceptForm(),
            'uid': uid,
            'target': target,
            'idp': request.query_params.get('idp'),
            'idp_token': request.query_params.get('idp_token'),
        },
    )


@router.post('/auth/accept')
def accept_post():
    """Require the user to accept the privacy policy.

    If the policy is accepted, redirect back to the target with a new token.
    If the policy is not accepted, redirect back to the target with an error.
    """

    form = ui.forms.AcceptForm()
    is_accepted = form.accept.data
    uid = form.uid.data
    target = form.target.data

    log.debug(f'Privacy policy accept form (POST): uid="{uid}" target="{target}"')

    if not is_accepted:
        log.warn(f'Refused privacy policy: uid="{uid}" target="{target}"')
        return util.redirect(
            target,
            error='Login unsuccessful: Privacy policy not accepted',
        )

    log.debug(f'Accepted privacy policy: uid="{uid}" target="{target}"')

    udb = UserDb()
    udb.set_accepted(uid=uid)

    return util.redirect(
        target,
        token=udb.get_token(uid=uid),
        cname=udb.get_cname(uid=uid),
        idp=request.query_params.get('idp'),
        idp_token=request.query_params.get('idp_token'),
    )
