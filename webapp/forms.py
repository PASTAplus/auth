""":Mod: forms

:Synopsis:

:Author:
    servilla

:Created:
    10/17/19
"""
import daiquiri

# from flask_wtf import FlaskForm
# from wtforms import BooleanField, HiddenField, SubmitField

log = daiquiri.getLogger(__name__)


class AcceptForm(FlaskForm):
    pass
    # accept = BooleanField('Accept')
    # target = HiddenField()
    # uid = HiddenField()
    # submit = SubmitField('Submit')
    # idp = HiddenField()
    # idp_token = HiddenField()
