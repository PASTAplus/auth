import pprint

import db.models.permission
from config import Config


def get_resource_tree_for_ui(resource_query):
    tree_list = _get_resource_tree(resource_query)

    def build_nodes(resource_dict):
        r = resource_dict

        # r['key'] = r['resource_row'].key ### for testing
        r['resource_id'] = r['resource_row'].id
        r['parent_id'] = r['resource_row'].parent_id
        r['label'] = r['resource_row'].label
        r['type'] = r['resource_row'].type

        for child_resource in resource_dict['children']:
            build_nodes(child_resource)

        _prune_dict(
            resource_dict,
            {
                # 'key', ### for testing
                'resource_id',
                # 'parent_id',
                'label',
                'type',
                'children',
                'principals',
            },
        )

        for principal_dict in resource_dict['principals']:
            principal_dict['permission_level'] = db.models.permission.get_permission_level_enum(
                principal_dict['rule_row'].permission
            ).value

            _prune_dict(
                principal_dict,
                {
                    # 'key', ### for testing
                    'principal_type',
                    'edi_id',
                    'title',
                    'description',
                    'permission_level',
                },
            )

    for resource_dict in tree_list:
        build_nodes(resource_dict)

    return tree_list


def get_resource_tree_for_api(resource_query, include_principals=False):
    tree_list = _get_resource_tree(resource_query)
    for resource_dict in tree_list:
        walk_recursive(resource_dict, include_principals)
    return tree_list


def walk_recursive(resource_dict, include_principals):
    r = resource_dict
    r['key'] = r['resource_row'].key
    for child_resource in resource_dict['children']:
        walk_recursive(child_resource, include_principals)
    _prune_dict(
        resource_dict,
        {
            'key',
            # 'parent_id',
            # 'label',
            # 'type',
            # 'principal_dict',
            'children',
            'principals',
        },
    )
    for principal_dict in resource_dict['principals']:
        _prune_dict(
            principal_dict,
            {
                'principal_type',
                'edi_id',
                'title',
                'description',
                'permission',
            },
        )


def _prune_dict(d, keep_key_set):
    """Inline prune a dict to only keep the keys in the keep_key_set."""
    for have_key in list(d.keys()):
        if have_key not in keep_key_set:
            del d[have_key]


# noinspection PyProtectedMember
# ._mapping used below is a private attribute of the SQLAlchemy Row object, but is commonly used
# in client code.
def _get_resource_tree(resource_query):
    """Get a tree of resources with permissions as a list of nested dicts."""
    tree_dict = {}

    # 1st pass: build flat dict of resources, each with corresponding principals
    for (
        resource_row,
        rule_row,
        principal_row,
        profile_row,
        group_row,
    ) in resource_query:
        assert (profile_row is None) != (
            group_row is None
        ), 'db.models.profile.Profile OR db.models.profile.Group must be present'

        rule_row.permission = db.models.permission.get_permission_level_enum(
            rule_row.permission
        ).name

        resource_dict = tree_dict.setdefault(
            resource_row.id,
            {
                'resource_row': resource_row,
                'principal_dict': {},
                'children': [],
            },
        )

        principal_type = 'profile' if profile_row is not None else 'group'

        norm_dict = (
            {
                'principal_type': 'profile',
                'edi_id': profile_row.edi_id,
                'title': profile_row.common_name,
                'description': profile_row.email,
                'permission': db.models.permission.get_permission_level_enum(
                    rule_row.permission
                ).name,
            }
            if principal_type == 'profile'
            else {
                'principal_type': 'group',
                'edi_id': group_row.edi_id,
                'title': group_row.name,
                'description': group_row.description,
                'permission': db.models.permission.get_permission_level_enum(
                    rule_row.permission
                ).name,
            }
        )

        resource_dict['principal_dict'][principal_row.id] = {
            'principal_row': principal_row,
            'principal_type': principal_type,
            'profile_row': profile_row,
            'group_row': group_row,
            'rule_row': rule_row,
            **norm_dict,
        }

        resource_dict['principals'] = _principal_dict_to_sorted_list(
            resource_dict['principal_dict']
        )

    # 2nd pass

    # Map children to parents. This is done in a second pass to ensure all potential parents are
    # already available in the dict.
    for resource_id, resource_dict in tree_dict.items():
        parent_id = resource_dict['resource_row'].parent_id
        if parent_id:
            # A valid database will always have higher or equal permissions on parents as on
            # children. But test databases may not fill that requirement, with the result that a
            # child may reference a parent that does not exist in a query result that is filtered
            # on permissions (while the parent does exist in the DB)
            if parent_id in tree_dict:
                tree_dict[parent_id]['children'].append(resource_dict)
            else:
                # The parent is missing, so we move this resource to the root level.
                resource_dict['parent_id'] = None

    # Collect the root nodes. Only root nodes need to be added to the tree_list, as they are
    # ancestors of the rest of the nodes.
    tree_list = []
    for resource_id, resource_dict in tree_dict.items():
        parent_id = resource_dict['resource_row'].parent_id
        if parent_id is None:
            tree_list.append(resource_dict)

    # Sort siblings in the tree by resource labels.
    # _sort_siblings_recursive(tree_list)

    return tree_list


def _sort_siblings_recursive(child_list):
    """Inline sort siblings in the resource tree by resource labels."""
    for resource_dict in child_list:
        resource_dict['children'] = sorted(resource_dict['children'], key=_get_sibling_sort_key)
        for child_resource in resource_dict['children']:
            _sort_siblings_recursive(child_resource['children'])


def _principal_dict_to_sorted_list(principal_dict):
    return sorted(principal_dict.values(), key=_get_principal_sort_key)


def _get_sibling_sort_key(resource_dict):
    """Key for sorting resources."""
    r = resource_dict['resource_row']
    return (
        r.type or '',
        r.label or '',
        r.key,
    )


def _get_principal_sort_key(principal_dict):
    """Key for sorting principals"""
    p = principal_dict
    title, description, edi_id = p['title'], p['description'], p['edi_id']
    # Sort principals with no title at the end by prepending \uffff, a high unicode character, to
    # the edi_id.
    if not title:
        title = '\uffff' + edi_id
    # Sort the Public user to the top
    if p['edi_id'] == Config.PUBLIC_EDI_ID:
        title = ''
    # Sort the authenticated user after the Public user and before all others
    elif p['edi_id'] == Config.AUTHENTICATED_EDI_ID:
        title = ' '
    return title, description, edi_id
