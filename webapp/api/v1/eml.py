"""EML API v1: Bulk resource creation via EML
"""
import uuid

import daiquiri
import fastapi
import lxml.etree
import sqlalchemy
import starlette.requests
import starlette.responses
import sqlalchemy.exc

import api.utils
import db.models.permission
import db.resource_tree
import util.dependency
import util.url
from config import Config
from db.models.permission import Resource
import util.exc

router = fastapi.APIRouter(prefix='/v1')

NS_DICT = {
    'eml': 'https://eml.ecoinformatics.org/eml-2.2.0',
    'pasta': 'pasta://pasta.edirepository.org/service-0.1',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
}

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

# 12d64e299f434a99ae43552ce247723b
# https://pasta-d.lternet.edu/package/data/eml/knb-lter-arc/1406/6/bd3c0df24143a8a7eb72e01bc879df20
# https://pasta-d.lternet.edu/package/eml/knb-lter-arc/1402/6
# https://pasta-d.lternet.edu/package/metadata/eml/knb-lter-bes/584/301
# https://pasta-d.lternet.edu/package/report/eml/knb-lter-arc/1400/7

PACKAGE_KEY_FORMAT = 'https://pasta-d.lternet.edu/package/eml/{scope}/{identity}/{revision}'
DATA_ENTITY_KEY_FORMAT = (
    'https://pasta-d.lternet.edu/package/data/eml/{scope}/{identity}/{revision}/{authentication}'
)

# Register the namespaces globally. This affects serialization and deserialization, not methods like
# xpath().
for k, v in NS_DICT.items():
    lxml.etree.register_namespace(k, v)


log = daiquiri.getLogger(__name__)


@router.post('/eml')
async def post_v1_eml(
    request: starlette.requests.Request,
    dbi: util.dependency.DbInterface = fastapi.Depends(util.dependency.dbi),
    token_profile_row: util.dependency.Profile = fastapi.Depends(util.dependency.token_profile_row),
):
    """addEML(): Create a resource for access control

    (1) If no access rules at all, only the owner has access to the package resources
    (2) If access rules only at the dataset level, then those access rules apply to any and all data entities
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
            request, api_method, 'Must be in the Vetted system group to create a resource'
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
        await create_eml_permissions(token_profile_row, dbi, eml_etree)
    except sqlalchemy.exc.IntegrityError as e:
        await dbi.rollback()
        return api.utils.get_response_400_bad_request(
            request, api_method, f'Error creating EML resource: {e}'
        )
    return api.utils.get_response_200_ok(request, api_method, 'EML resources created successfully')


async def create_eml_permissions(token_profile_row, dbi, eml_etree):
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
    # Create the root resource for the package
    package_resource_key = PACKAGE_KEY_FORMAT.format(scope=scope, identity=identity, revision=revision)
    log.debug(f'Creating root resource: {package_resource_key}')
    package_resource_row = await dbi.create_owned_resource(
        token_profile_row, None, package_resource_key, package_id, 'package'
    )
    dbi.flush()
    # Get the optional <access> element at the root of the EML. This will be our fallback access for
    # all cases where there's no entity level access element.
    root_access_el = eml_etree.find('access')
    # Iterate over data entities (dataTable, spatialRaster, spatialVector, storedProcedure, view,
    # and otherEntity). The <dataset> element contains many direct children which we are not
    # interested in. We are only interested in data entities, and we can find them by checking for
    # an <entityName> child.
    for entity_name_el in eml_etree.xpath('/eml:eml/dataset/*/entityName', namespaces=NS_DICT):
        entity_name = entity_name_el.text
        log.debug(f'Processing entity: {entity_name}')
        # Create the resource for the data entity.
        data_resource_key = DATA_ENTITY_KEY_FORMAT.format(entity_name=entity_name)
        data_resource_row = await dbi.create_owned_resource(
            token_profile_row, package_resource_row.id, data_resource_key, package_id, 'package'
        )
        # We can now go up to the parent element, which is a data entity element.
        data_entity_el = entity_name_el.getparent()
        # print(data_entity_el.tag)
        physical_el = data_entity_el.find('physical')
        if physical_el is None:
            raise util.exc.EmlError(f'No <physical> element found for entity: {entity_name}')
        # log.debug(physical_el)
        authentication_el = physical_el.find('authentication')
        if authentication_el is None:
            raise util.exc.EmlError(f'No <authentication> element found for entity: {entity_name}')
        # log.debug(authentication_el.text)
        # Get the data entity's access element, if it exists. Fall back to the root access element
        # if the data entity does not have its own access element. If there was no root access
        # either, then there are no access rules to add for this entity.
        try:
            data_access_el = physical_el.xpath('distribution/access', namespaces=NS_DICT)[0]
        except IndexError:
            data_access_el = None
        access_el = data_access_el or root_access_el
        log.error(f'access_el: {access_el}')
        # Process the access element
        # Due to rule (4), if there is a data access element, we need to apply the data access el to
        # the package.
        if data_access_el is not None:
            await _process_access_element(token_profile_row, dbi, package_resource_row, access_el)
        if access_el is not None:
            await _process_access_element(token_profile_row, dbi, data_resource_row, access_el)


async def _process_access_element(token_profile_row, dbi, resource_row, access_el):
    # Iterate over access elements
    # print(f'  Access System: {access.get("system")}')
    # print(f'  Auth System: {access.get("authSystem")}')
    # print(f'  Order: {access.get("order")}')

    # Iterate over allow elements
    for allow_el in access_el.xpath('allow', namespaces=NS_DICT):
        principal = allow_el.find('principal', namespaces=NS_DICT)
        permission = allow_el.find('permission', namespaces=NS_DICT)


        # print(f'    Principal: {principal.text}')
        # print(f'    Permission: {permission.text}')
        log.debug(' - '.join((method_name, principal.text, permission.text)))

        resource_row = await dbi.create_resource(
            parent_id=None,
            key=f'{Config.API_KEY_PREFIX}{method_name}-{uuid.uuid4()}',
            label=f'Service Method: {method_name}',
            type_str=Config.API_TYPE,
        )


