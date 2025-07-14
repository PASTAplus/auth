"""Tests for resource management in the database interface
"""

import pytest
import sqlalchemy.exc

pytestmark = [
    pytest.mark.asyncio,
    # pytest.mark.order(40),
]


async def test_create_resource(populated_dbi):
    """Create a resource with a valid resource key."""
    resource_row = await populated_dbi.create_resource(
        parent_id=None,
        key='test_key',
        label='Test Resource',
        type_str='testResource',
    )
    assert resource_row is not None
    assert resource_row.key == 'test_key'
    assert resource_row.label == 'Test Resource'
    assert resource_row.type == 'testResource'
    assert resource_row.parent_id is None


async def test_create_resource_duplicate_key(populated_dbi):
    """Attempt to create a resource with a duplicate resource key."""
    await populated_dbi.create_resource(
        parent_id=None,
        key='test_key',
        label='Test Resource',
        type_str='testResource',
    )
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        await populated_dbi.create_resource(
            parent_id=None,
            key='test_key',
            label='Duplicate Resource',
            type_str='testResource',
        )


# async def test_update_resource_details(populated_dbi):
#     """Update the details of an existing resource."""
#     resource_row = await populated_dbi.create_resource(
#         key='test_key',
#         label='Test Resource',
#         type_str='testResource',
#         parent_id=None,
#     )
#     updated_row = await populated_dbi.update_resource_details(
#         resource_row.id,
#         label='Updated Resource',
#         type_str='updatedResourceType',
#     )
#     assert updated_row.label == 'Updated Resource'
#     assert updated_row.type == 'updatedResourceType'
#
#
# async def test_resource_move_to_another_parent(populated_dbi):
#     pass


