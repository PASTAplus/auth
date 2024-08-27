import daiquiri
import fastapi
import starlette.requests
import starlette.templating

import user_db
import util
from config import Config

log = daiquiri.getLogger(__name__)
router = fastapi.APIRouter()
templates = starlette.templating.Jinja2Templates(Config.HERE_PATH / 'templates')


@router.get('/login/accept')
async def accept_get(request: starlette.requests.Request):
    """Require the user to accept the privacy policy.

    This only serves the form. The form submission is handled by accept_post().
    """
    target = request.query_params.get('target')
    # TODO: Current clients cannot provide idp_name for LDAP logins, so we default to
    # idp_name to 'ldap' for now. This should be removed once clients start using the
    # new flow.
    idp_name = request.query_params.get('idp_name', 'ldap')
    uid = request.query_params.get('uid')

    log.debug(f'Privacy policy accept form (GET): target="{target}" uid="{uid}"')

    return templates.TemplateResponse(
        'accept.html',
        {
            'request': request,
            'target': request.query_params.get('target'),
            'idp_name': idp_name,
            'uid': request.query_params.get('uid', ''),
            'idp_token': request.query_params.get('idp_token', ''),
        },
    )


@router.post('/login/accept')
async def accept_post(
    request: starlette.requests.Request,
    udb: user_db.UserDb = fastapi.Depends(user_db.udb),
):
    """Require the user to accept the privacy policy.

    If the policy is accepted, redirect back to the target with a new token.
    If the policy is not accepted, redirect back to the target with an error.
    """
    form = await request.form()
    target = form.get('target')
    idp_name = form.get('idp_name')
    uid = form.get('uid')
    is_accepted = form.get('action') == 'accept'

    log.debug(f'Privacy policy accept form (POST): target="{target}" idp_name="{idp_name}" uid="{uid}"')

    if not is_accepted:
        log.warn(f'Privacy policy not accepted: target="{target}" idp_name="{idp_name}" uid="{uid}"')
        return util.redirect(
            target,
            error='Login unsuccessful: Privacy policy not accepted',
        )

    identity_row = udb.get_identity(idp_name=idp_name, uid=uid)

    udb.set_privacy_policy_accepted(identity_row.profile.urid)

    log.debug(f'Privacy policy accepted: target="{target}" idp_name="{idp_name} "uid="{uid}"')

    # TODO: Make sure that this cookie is no longer required.
    # if form.get('idp_name') == 'ldap':
    #     response = starlette.responses.RedirectResponse(target)
    #     response.set_cookie('auth-token', identity_row.pasta_token)
    #     return response

    return util.redirect_target(
        target=form.get('target'),
        pasta_token=identity_row.pasta_token,
        urid=identity_row.profile.urid,
        full_name=identity_row.profile.full_name,
        email=identity_row.profile.email,
        uid=identity_row.uid,
        idp_name=identity_row.idp_name,
        idp_token=form.get('idp_token', ''),
    )
