#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: forms

:Synopsis:

:Author:
    servilla

:Created:
    10/17/19
"""
import daiquiri
from flask_wtf import FlaskForm
from wtforms import BooleanField, HiddenField, SubmitField, StringField
from wtforms.validators import DataRequired

logger = daiquiri.getLogger('forms: ' + __name__)


class AcceptForm(FlaskForm):
    accept = BooleanField('Accept')
    target = HiddenField()
    uid = HiddenField()
    submit = SubmitField('Submit')

