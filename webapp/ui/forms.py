import daiquiri
import fastapi

# from wtforms import BooleanField, HiddenField, SubmitField
import starlette.responses
import starlette.requests

log = daiquiri.getLogger(__name__)


class AcceptForm:
    pass
    # accept = BooleanField('Accept')
    # target = HiddenField()
    # uid = HiddenField()
    # submit = SubmitField('Submit')
    # idp_name = HiddenField()
    # idp_token = HiddenField()
