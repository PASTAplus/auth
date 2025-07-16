"""Tests for ACR management in the database interface
"""
import tests.sample
import logging

import pytest
import sqlalchemy

import db.models.permission
import db.resource_tree
import tests.edi_id
import tests.sample

TEST_TREE = {
    'r0': {
        'r1': {
            'r2': {
                'r3': {},
                'r4': {},
            },
            'r5': {
                'r6': {},
                'r7': {},
            },
        },
        'r8': {
            'r9': {
                'r10': {
                    'r11': {},
                },
                'r12': {
                    'r13': {},
                },
            },
            'r14': {
                'r15': {
                    'r16': {},
                },
                'r17': {
                    'r18': {},
                },
            },
        },
    }
}

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(40),
]

log = logging.getLogger(__name__)


async def test_get_principal_by_edi_id(populated_dbi):
    """Get a principal by EDI-ID."""
    principal_row = await populated_dbi.get_principal_by_edi_id(tests.edi_id.JOHN)
    # ID from the DB fixture
    assert principal_row.id == 5


async def test_get_equivalent_principal_edi_id_set_1(populated_dbi, john_profile_row):
    """Get the set of EDI-IDs that are equivalent to John's EDI-ID."""
    john_edi_id_set = await populated_dbi.get_equivalent_principal_edi_id_set(john_profile_row)
    # John is a member of 7 groups, and gets the default public and anonymous equivalents. Including
    # himself, this should be 10 EDI-IDs.
    assert len(john_edi_id_set) == 10
    tests.sample.assert_match(john_edi_id_set, 'get_equivalent_principal_edi_id_set_1.json')


async def test_equivalent_principal_edi_id_set_for_public(populated_dbi):
    """Attempt to get equivalents for the public or authenticated users -> AssertionError"""
    profile_row = await populated_dbi.get_public_profile()
    with pytest.raises(AssertionError):
        await populated_dbi.get_equivalent_principal_edi_id_set(profile_row)
    profile_row = await populated_dbi.get_authenticated_profile()
    with pytest.raises(AssertionError):
        await populated_dbi.get_equivalent_principal_edi_id_set(profile_row)


async def test_get_resource_ancestors_level_3(populated_dbi):
    """Retrieve ancestors of resource at level 3 in tree -> All expected ancestors"""
    id_dict = await _build_test_tree(populated_dbi)
    expected_id_set = _get_expected_id_set(id_dict, 'r0/r8/r14/r15')
    received_id_set = set(await populated_dbi.get_resource_ancestors_id_set((id_dict['r15'],)))
    # The test function returns the IDs of the ancestors, excluding the given resource IDs.
    expected_id_set -= {id_dict['r15']}
    assert received_id_set == expected_id_set


async def test_get_resource_ancestors_level_0(populated_dbi):
    """Retrieve ancestors of root resource -> Empty set"""
    id_dict = await _build_test_tree(populated_dbi)
    received_id_set = set(await populated_dbi.get_resource_ancestors_id_set((id_dict['r0'],)))
    assert not received_id_set


async def test_get_resource_descendants(populated_dbi):
    """Retrieve descendants of resource at level 2 in tree -> All expected descendants"""
    id_dict = await _build_test_tree(populated_dbi)
    expected_id_set = _get_expected_id_set(id_dict, 'r8/r9/r10/r11/r12/r13/r14/r15/r16/r17/r18')
    received_id_set = set(await populated_dbi.get_resource_descendants_id_set((id_dict['r8'],)))
    assert received_id_set == expected_id_set


async def test_get_resource_generator_1(populated_dbi, john_profile_row):
    """Test permission generator filtering. It should only return resources which the caller has
    the given permission on.
    """
    await _build_test_tree(populated_dbi)
    resource_row = await populated_dbi.get_resource('r0')
    # John has no permissions on 'r0'
    rule_row = await populated_dbi.get_rule(resource_row, john_profile_row.principal)
    assert rule_row is None
    # John cannot retrieve permissions for 'r0'
    rows = [
        row
        async for row in populated_dbi.get_resource_generator(
            john_profile_row, (resource_row.id,), db.models.permission.PermissionLevel.READ
        )
    ]
    assert not rows
    # We now give John read permission on 'r0'
    await populated_dbi.create_or_update_rule(
        resource_row,
        john_profile_row.principal,
        db.models.permission.PermissionLevel.READ,
    )
    # John can now retrieve permissions for 'r0' at 'read' level
    rows = [
        row
        async for row in populated_dbi.get_resource_generator(
            john_profile_row, (resource_row.id,), db.models.permission.PermissionLevel.READ
        )
    ]
    assert len(rows) == 1
    # John cannot retrieve permissions for 'r0' at write level
    rows = [
        row
        async for row in populated_dbi.get_resource_generator(
            john_profile_row, (resource_row.id,), db.models.permission.PermissionLevel.WRITE
        )
    ]
    assert not rows


async def test_get_resource_tree_for_ui(populated_dbi, john_profile_row):
    """Get a resource tree for the UI, based on John's permissions."""
    # Get all resource IDs
    resource_id_list = [r.id for r in await _get_all_resources_list(populated_dbi)]
    # Get permissions for John on all resources at 'read' level
    rows = [
        row
        async for row in populated_dbi.get_resource_generator(
            john_profile_row, resource_id_list, db.models.permission.PermissionLevel.READ
        )
    ]
    resource_tree = db.resource_tree.get_resource_tree_for_ui(rows)
    tests.sample.assert_match(resource_tree, 'get_resource_tree_for_ui.json')


async def test_get_resource_tree_for_api(populated_dbi, john_profile_row):
    """Get a resource tree for the API, based on John's permissions."""
    # Get all resource IDs
    resource_id_list = [r.id for r in await _get_all_resources_list(populated_dbi)]
    # Get permissions for John on all resources at 'read' level
    rows = [
        row
        async for row in populated_dbi.get_resource_generator(
            john_profile_row, resource_id_list, db.models.permission.PermissionLevel.READ
        )
    ]
    resource_tree = db.resource_tree.get_resource_tree_for_api(rows)
    tests.sample.assert_match(resource_tree, 'get_resource_tree_for_api.json')


async def test_create_or_update_rule(populated_dbi, john_profile_row):
    """Test creating a new permission."""
    resource_row = await populated_dbi.create_resource(None, 'a-resource-key', 'A Resource', 'test-type')
    permission_level = db.models.permission.PermissionLevel.WRITE
    await populated_dbi.create_or_update_rule(
        resource_row, john_profile_row.principal, permission_level
    )
    rule_row = await populated_dbi.get_rule(resource_row, john_profile_row.principal)
    assert rule_row is not None
    assert rule_row.permission == permission_level


async def _get_all_resources_list(populated_dbi):
    result = await populated_dbi.execute(sqlalchemy.select(db.models.permission.Resource))
    return result.scalars().all()


async def _build_test_tree(populated_dbi):
    """Build a tree of resources from the given recursive structure."""
    id_dict = {}

    async def _build(d, parent_id=None, indent=0):
        for key, sub_child_dict in d.items():
            resource_row = await populated_dbi.get_resource(key)
            if not resource_row:
                resource_row = await populated_dbi.create_resource(parent_id, key, key, 'test-type')
            id_dict[key] = resource_row.id
            # log.info(f'{" " * indent}{key} = {resource_row.id}')
            await _build(sub_child_dict, resource_row.id, indent + 4)

    await _build(TEST_TREE, None)

    return id_dict


def _get_expected_id_set(id_dict, path):
    """Get the expected IDs for the given path."""
    return {id_dict[key] for key in path.split('/')}
