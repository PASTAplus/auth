import datetime
import enum

import daiquiri
import sqlalchemy.orm

import db.models.base

log = daiquiri.getLogger(__name__)


#
# Tables for optimizing tree traversal
#


class RootResource(db.models.base.Base):
    __tablename__ = 'root'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    root_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('resource.id'), nullable=False, index=True
    )
    label = sqlalchemy.Column(sqlalchemy.String, nullable=True, index=True)
    type = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    root_node = sqlalchemy.orm.relationship(
        'Resource',
        # back_populates='resource',
        #     cascade_backrefs=False,
        #     cascade='all, delete-orphan',
    )
