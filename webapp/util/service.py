import asyncio
import sys
import lxml.etree

from config import Config

SERVICE_XML_PATH = Config.ASSETS_PATH / 'service.xml'

NS = {
    'pasta': 'pasta://pasta.edirepository.org/service-0.1',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
}

# Register the namespaces globally. This affects serialization and deserialization, not methods like
# xpath().
for k, v in NS.items():
    lxml.etree.register_namespace(k, v)

# Sample XML content for the service definition.
# <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
# <pasta:service
#     xmlns:pasta="pasta://pasta.edirepository.org/service-0.1"
#     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
#     xsi:schemaLocation="pasta://pasta.edirepository.org/service-0.1 http://nis.lternet.edu/schemas/pasta/pasta-service.xsd"
#     >
#
#     <pasta:service-method name="appendProvenance">
#         <access
#             system="https://pasta.edirepository.org"
#             authSystem="https://pasta.edirepository.org/authentication"
#             order="allowFirst">
#             <allow>
#                 <principal>pasta</principal>
#                 <permission>write</permission>
#             </allow>
#             <allow>
#                 <principal>authenticated</principal>
#                 <permission>write</permission>
#             </allow>
#             <allow>
#                 <principal>public</principal>
#                 <permission>write</permission>
#             </allow>
#         </access>
#     </pasta:service-method>
#
#     <pasta:service-method name="createDataPackage">
#         <access
#             system="https://pasta.edirepository.org"
#             authSystem="https://pasta.edirepository.org/authentication"
#             order="allowFirst">
#             <allow>
#                 <principal>pasta</principal>
#                 <permission>write</permission>
#             </allow>
#             <allow>
#                 <principal>vetted</principal>
#                 <permission>write</permission>
#             </allow>
#         </access>
#     </pasta:service-method>
# </pasta:service>


async def main():
    await print_service_xml()
    return 0


async def print_service_xml():
    # Parse the XML to etree with lxml
    root = lxml.etree.parse(SERVICE_XML_PATH).getroot()

    # Iterate over pasta:service-method
    for service_method in root.xpath('//pasta:service-method', namespaces=NS):
        method_name = service_method.get('name')
        # print(f'Service Method: {method_name}')

        # Iterate over access elements
        for access in service_method.xpath('./access', namespaces=NS):
            # print(f'  Access System: {access.get("system")}')
            # print(f'  Auth System: {access.get("authSystem")}')
            # print(f'  Order: {access.get("order")}')

            # Iterate over allow elements
            for allow in access.xpath('./allow', namespaces=NS):
                principal = allow.find('principal', namespaces=NS)
                permission = allow.find('permission', namespaces=NS)
                # print(f'    Principal: {principal.text}')
                # print(f'    Permission: {permission.text}')

                print(' - '.join([method_name, principal.text, permission.text]))

    # Convert etree to a string with pretty print
    pretty_xml = lxml.etree.tostring(
        root, pretty_print=True, encoding='UTF-8', xml_declaration=True
    ).decode('UTF-8')
    # print(pretty_xml)


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
