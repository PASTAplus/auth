# Resource Management API

- [Index](index.md) - API Documentation
- [Parameters](parameters.md) - API Parameter Details
- [Profiles](profile.md) - Create and manage user profiles
- [Resources](resource.md) - Create and manage resources
- [Rules](rule.md) - Create and manage the ACRs for resources

This document describes the API for managing resources for access control.

## Create Resource

Create a resource for access control.

The token profile becomes the owner of the resource. 

```
POST: /auth/v1/resource

createResource(
  jwt_token
  resource_key: Unique resource key of the resource
  resource_label: Human readable name of the resource
  resource_type: Type of resource
  parent_resource_key: Resource key of the parent (set to `None` to create a top-level resource)
)

Returns:
  200 OK
  400 Bad Request
  401 Unauthorized
  403 Forbidden

Permissions:
  authenticated: changePermission
```

### Status codes

- `200 OK`
  - A new resource was created.

- `400 Bad Request`
  - In addition to possible reasons outlined in [Parameters](parameters.md):
    - A resource with the same key already exists

### Examples

Example request using curl and JSON:

```shell
curl -X POST https://auth.edirepository.org/auth/v1/resource \
-H "Cookie: jwt_token=$(<myjwt.txt)" \
-d '{
  "resource_key": "https://pasta.lternet.edu/package/data/eml/edi/643/4/87c390495ad405e705c09e62ac6f58f0",
  "resource_label": "edi.643.4",
  "resource_type": "package",
  "parent_resource_key": null
}'
```

Example JSON `200 OK` response:

```json
{
  "method": "createResource",
  "msg": "Resource created successfully",
  "resource_key": "https://pasta.lternet.edu/package/data/eml/edi/643/4/87c390495ad405e705c09e62ac6f58f0"
}
```

Example request using curl and XML:

```shell
curl -X POST https://auth.edirepository.org/auth/v1/resource \
-H "Cookie: jwt_token=$(<myjwt.txt)" \
-H "Content-Type: text/xml" \
-d '{
  "resource_key": "https://pasta.lternet.edu/package/data/eml/edi/643/4/87c390495ad405e705c09e62ac6f58f0",
  "resource_label": "edi.643.4",
  "resource_type": "package",
  "parent_resource_key": null
}'
```

Example XML `200 OK` Response

```xml
<result>
  <method>createResource</method>
  <msg>Resource created successfully</msg>
  <resource_key>https://pasta.lternet.edu/package/data/eml/edi/643/4/87c390495ad405e705c09e62ac6f58f0</resource_key>
</result>
```
