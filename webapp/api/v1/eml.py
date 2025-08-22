"""EML API v1: Bulk resource creation via EML"""
import uuid

import daiquiri
import fastapi
import lxml.etree
import sqlalchemy
import sqlalchemy.exc
import starlette.requests
import starlette.responses

import api.utils
import db.models.permission
import db.resource_tree
import util.dependency
import util.edi_id
import util.exc
import util.url
from config import Config

router = fastapi.APIRouter(prefix='/v1')

# NS_DICT = {
#     'eml': 'https://eml.ecoinformatics.org/eml-2.2.0',
#     'pasta': 'pasta://pasta.edirepository.org/service-0.1',
#     'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
# }

SYSTEM_PRINCIPAL_MAP = {
    'public': Config.PUBLIC_EDI_ID,
    'authenticated': Config.AUTHENTICATED_EDI_ID,
    'vetted': Config.VETTED_GROUP_EDI_ID,
}

PERMISSION_LEVEL_MAP = {
    'read': db.models.permission.PermissionLevel.READ,
    'write': db.models.permission.PermissionLevel.WRITE,
    'all': db.models.permission.PermissionLevel.CHANGE,
}

PACKAGE_KEY_FORMAT = '{}/package/eml/{}/{}/{}'
EML_KEY_FORMAT = '{}/package/metadata/eml/{}/{}/{}'
REPORT_KEY_FORMAT = '{}/package/report/eml/{}/{}/{}'

log = daiquiri.getLogger(__name__)


@router.post('/eml')
async def post_v1_eml(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """addEML(): Create a resource for access control
    (1) If no access rules at all, only the owner has access to the package resources
    (2) If access rules only at the dataset level, then those access rules apply to any and all data
    entities
    (3) If any data entity has an access rule, then it takes precedence over data set rules
    (4) If a user has READ or higher permission on a data entity, but not at the dataset level, they
    will still be denied access to the data entity
    """
    api_method = 'addEML'
    # Check token
    if token_profile_row is None:
        return api.utils.get_response_401_unauthorized(request, api_method)
    # Check that the token is in the Vetted system group
    if not await dbi.is_vetted(token_profile_row):
        return api.utils.get_response_403_forbidden(
            request, api_method, 'Must be in the Vetted system group to create resources'
        )
    # Check that the request body is valid JSON
    try:
        request_dict = await api.utils.request_body_to_dict(request)
    except ValueError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Invalid JSON in request body: {e}'
        )
    # Check that the request contains the required fields
    try:
        eml_str = request_dict['eml']
        key_prefix = request_dict['key_prefix']
    except KeyError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Missing field in JSON in request body: {e}'
        )
    # Parse EML to etree and check that it's well-formed XML
    try:
        eml_etree = lxml.etree.fromstring(eml_str.encode('utf-8'))
    except lxml.etree.XMLSyntaxError as e:
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Error parsing EML XML: {e}'
        )
    # Create resources and permissions for the EML
    try:
        await create_eml_permissions(token_profile_row, dbi, key_prefix, eml_etree)
    except util.exc.EmlError as e:
        await dbi.rollback()
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Error creating resource: {e}'
        )
    return api.utils.get_response_200_ok(request, api_method, 'Resources created successfully')


async def create_eml_permissions(token_profile_row, dbi, key_prefix, eml_etree):
    # <eml:eml packageId="icarus.3.1" system="https://pasta.edirepository.org"
    # get the packageId
    package_id = eml_etree.get('packageId')
    if package_id is None:
        raise util.exc.EmlError('No packageId found in EML root element')
    # Get the scope, identity, and revision from the packageId
    try:
        scope, identity, revision = package_id.split('.')
        identity = int(identity)
        revision = int(revision)
    except ValueError:
        raise util.exc.EmlError(
            f'Invalid packageId format: "{package_id}". Expected format: scope.identity.revision'
        )
    # Get the optional <access> element at the root of the EML. This will be our fallback access for
    # all cases where there's no entity level access element.
    root_access_el = eml_etree.find('access')
    # Create the root resource for the package.
    package_key = PACKAGE_KEY_FORMAT.format(key_prefix, scope, identity, revision)
    package_resource_row = await _create_permission(
        token_profile_row,
        dbi,
        None,
        package_key,
        package_id,
        'package',
        root_access_el,
    )
    # Create the Metadata branch of the resource tree.
    metadata_resource_row = await _create_permission(
        token_profile_row,
        dbi,
        package_resource_row,
        uuid.uuid4().hex,
        'Metadata',
        'collection',
        root_access_el,
    )
    await _create_permission(
        token_profile_row,
        dbi,
        metadata_resource_row,
        EML_KEY_FORMAT.format(key_prefix, scope, identity, revision),
        'EML Metadata',
        'metadata',
        root_access_el,
    )
    await _create_permission(
        token_profile_row,
        dbi,
        metadata_resource_row,
        REPORT_KEY_FORMAT.format(key_prefix, scope, identity, revision),
        'Quality Report',
        'report',
        root_access_el,
    )
    # Create the Data branch of the resource tree.
    data_resource_row = await _create_permission(
        token_profile_row,
        dbi,
        package_resource_row,
        uuid.uuid4().hex,
        'Data',
        'collection',
        root_access_el,
    )
    # Iterate over data entities (dataTable, spatialRaster, spatialVector, storedProcedure, view,
    # and otherEntity). The <dataset> element contains many direct children which we are not
    # interested in. We are only interested in data entities, which we find by checking for an
    # <entityName> child.
    for entity_name_el in eml_etree.xpath('.//dataset/*/entityName'):
        log.debug(f'Processing entity: {entity_name_el.text}')
        # We can now go up to the parent element, which is a data entity element.
        data_entity_el = entity_name_el.getparent()
        # Then down to physical element.
        physical_el = data_entity_el.find('physical')
        # The physical element and its children are optional in the EML schema, so we need to check
        # if they exist.
        if physical_el is None:
            raise util.exc.EmlError(
                f'No <physical> element found for entity: {entity_name_el.text}'
            )
        url_el = physical_el.find('distribution/online/url')
        if url_el is None:
            raise util.exc.EmlError(f'No <url> element found for entity: {entity_name_el.text}')
        try:
            # Get the data entity's access element, if it exists.
            data_access_el = physical_el.xpath('distribution/access')[0]
            # This entity has its own access element. To ensure that the entity can be reached, we
            # apply the access element to the parents, up to the root, as well.
            await _create_rules(dbi, data_resource_row, data_access_el)
            await _create_rules(dbi, package_resource_row, data_access_el)
        except IndexError:
            # Fall back to the root access element if the data entity does not have its own access
            # element.
            data_access_el = root_access_el
        # Create data entity permissions.
        await _create_permission(
            token_profile_row,
            dbi,
            data_resource_row,
            url_el.text,
            entity_name_el.text,
            'data',
            data_access_el,
        )


async def _create_permission(token_profile_row, dbi, parent_row, key, label, type_str, access_el):
    log.debug(f'Creating resource: {key} - ({label} - {type_str})')
    # Check if the resource already exists
    try:
        await dbi.get_resource(key)
        raise util.exc.EmlError(f'Resource already exists. key="{key}"')
    except sqlalchemy.exc.NoResultFound:
        pass
    resource_row = await dbi.create_owned_resource(
        token_profile_row, parent_row.id if parent_row else None, key, label, type_str
    )
    await dbi.flush()
    if access_el is not None:
        await _create_rules(dbi, resource_row, access_el)
    return resource_row


async def _create_rules(dbi, resource_row, access_el):
    """Create rules for the given resource based on the access element."""
    # Iterate over allow elements
    for allow_el in access_el.xpath('allow'):
        # print(f'  Access System: {access.get("system")}')
        # print(f'  Auth System: {access.get("authSystem")}')
        # print(f'  Order: {access.get("order")}')
        # Get principal
        principal_el = allow_el.find('principal')
        if principal_el is None:
            raise util.exc.EmlError('Missing <principal> element in <allow> element')
        permission_el = allow_el.find('permission')
        # A principal can be one of:
        # - A legacy shortcut for a system principal ('public', 'authenticated', 'vetted')
        # - An EDI-ID of a profile or group
        # - An IdP UID of a profile
        # - A legacy Google email address of a profile
        principal_str = SYSTEM_PRINCIPAL_MAP.get(principal_el.text, principal_el.text)
        # Get permission level
        if permission_el is None:
            raise util.exc.EmlError('Missing <permission> element in <allow> element')
        permission_level = PERMISSION_LEVEL_MAP.get(permission_el.text)
        if permission_level is None:
            raise util.exc.EmlError(
                f'Invalid permission level: {permission_el.text}. '
                f'Expected one of: {", ".join(PERMISSION_LEVEL_MAP.keys())}'
            )
        # The only way to get an EDI-ID is to create a profile or a group. So if the principal_str
        # is a well-formed EDI-ID, we just check if it exists in the DB as a profile or group, and
        # error out if not. An error probably here means that a user deleted their profile or group,
        # or the EML is being submitted to the wrong EDI IAM Service.
        if util.edi_id.is_well_formed_edi_id(principal_str):
            try:
                principal_row = await dbi.get_principal_by_edi_id(principal_str)
            except sqlalchemy.exc.NoResultFound:
                raise util.exc.EmlError(
                    f'A profile or group with EDI-ID "{principal_str}" does not exist'
                )
        else:
            profile_row = await _get_or_create_profile(dbi, principal_str)
            principal_row = await dbi.get_principal_by_edi_id(profile_row.edi_id)
        await dbi.create_or_update_rule(
            resource_row, principal_row, permission_level=permission_level
        )


async def _get_or_create_profile(dbi, principal_str):
    try:
        return (await dbi.get_identity_by_idp_uid(principal_str)).profile
    except sqlalchemy.exc.NoResultFound:
        try:
            # See README.md: Strategy for dealing with Google emails historically used as
            # identifiers
            return (await dbi.get_identity_by_email(principal_str)).profile
        except sqlalchemy.exc.NoResultFound:
            return (await dbi.create_skeleton_profile_and_identity(principal_str)).profile
    except sqlalchemy.exc.MultipleResultsFound:
        raise util.exc.EmlError(f'Multiple identities found for principal "{principal_str}". ')
