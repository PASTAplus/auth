"""Tables for optimizing searches, storing search results and related metadata"""
import daiquiri
import sqlalchemy.orm

import db.models.base

log = daiquiri.getLogger(__name__)


class RootResource(db.models.base.Base):
    __tablename__ = 'search_root'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    root_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('resource.id'), nullable=False, index=True
    )
    # Denormalized fields to speed up searches.
    label = sqlalchemy.Column(sqlalchemy.String, nullable=True, index=True)
    type = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)
    package_scope = sqlalchemy.Column(sqlalchemy.String, nullable=True, index=True)
    package_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=True, index=True)
    package_ver = sqlalchemy.Column(sqlalchemy.Integer, nullable=True, index=True)
    root_node = sqlalchemy.orm.relationship(
        'Resource',
        # back_populates='resource',
        #     cascade_backrefs=False,
        #     cascade='all, delete-orphan',
    )
    # Combined index across (type, package_scope, package_id, package_ver) to speed up package
    # searches.
    __table_args__ = (
        sqlalchemy.Index(
            'ix_root_type_scope_id_ver', 'type', 'package_scope', 'package_id', 'package_ver'
        ),
    )


class PackageScope(db.models.base.Base):
    __tablename__ = 'search_package_scope'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    scope = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=False)


class ResourceType(db.models.base.Base):
    __tablename__ = 'search_resource_type'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    type = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=True)


class SearchSession(db.models.base.Base):
    __tablename__ = 'search_session'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The profile of the user who performed this search.
    profile_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('profile.id'), nullable=False, index=True
    )
    # Unique identifier for the search session, used to track searches across requests.
    uuid = sqlalchemy.Column(sqlalchemy.String, unique=True, nullable=False)
    # The date and time the search session was first created and last accessed. These values are
    # used to determine if a search session is still active or has expired.
    created = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=sqlalchemy.func.now())
    accessed = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=sqlalchemy.func.now())
    # The search parameters used for the search session, stored as a JSON object.
    search_params = sqlalchemy.Column(sqlalchemy.JSON, nullable=False)
    # ORM relationship
    profile = sqlalchemy.orm.relationship(
        'db.models.profile.Profile',
        back_populates='search_sessions',
        cascade_backrefs=False,
    )
    # Search results associated with this search session.
    search_results = sqlalchemy.orm.relationship(
        'SearchResult',
        back_populates='search_session',
        cascade_backrefs=False,
        cascade='all, delete-orphan',
    )


class SearchResult(db.models.base.Base):
    """Store the search result that is associated with a search session. Only the root node of the
    search result is stored here. The rest of the tree is built on demand when the user expands the
    root node.
    """

    __tablename__ = 'search_result'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    # The search session this result belongs to.
    search_session_id = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('search_session.id'), nullable=False
    )
    # Sort order for the search result within the session.
    sort_order = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, index=False)
    # The resource ID of the search result. This is only used when the user expands the root node.
    resource_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    # Denormalized fields to avoid large join when scrolling through search results.
    resource_label = sqlalchemy.Column(sqlalchemy.String, nullable=True, index=False)
    resource_type = sqlalchemy.Column(sqlalchemy.String, nullable=False, index=False)
    # ORM relationship
    search_session = sqlalchemy.orm.relationship(
        'SearchSession',
        back_populates='search_results',
        cascade_backrefs=False,
    )
    __table_args__ = (
        # Ensure that the session and sort order are unique together. This is to help prevent
        # accidental duplicate entries in the search results for the same session.
        sqlalchemy.UniqueConstraint(
            'search_session_id', 'sort_order', name='uq_search_session_sort_order'
        ),
    )
