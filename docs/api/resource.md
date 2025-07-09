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
  edi_token
  resource_key: Unique resource key of the resource
  resource_label: Human readable name of the resource
  resource_type: Type of resource
  parent_key: Resource key of the parent (set to `None` to create a top-level resource)
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

Example request using cURL and JSON:

```shell
curl -X POST https://auth.edirepository.org/auth/v1/resource \
-H "Cookie: edi-token=$(<~/Downloads/token-EDI-<my-token>.jwt)" \
-d '{
  "resource_key": "https://pasta.lternet.edu/package/data/eml/edi/643/4/87c390495ad405e705c09e62ac6f58f0",
  "resource_label": "edi.643.4",
  "resource_type": "package",
  "parent_key": null
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

Example request using cURL and XML:

```shell
curl -X POST https://auth.edirepository.org/auth/v1/resource \
-H "Cookie: edi-token=$(<~/Downloads/token-EDI-<my-token>.jwt)" \
-H "Content-Type: text/xml" \
-d '{
  "resource_key": "https://pasta.lternet.edu/package/data/eml/edi/643/4/87c390495ad405e705c09e62ac6f58f0",
  "resource_label": "edi.643.4",
  "resource_type": "package",
  "parent_key": null
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

## Check Access

Check if the requesting client has access to a resource at the specified permission level.

```
GET: /auth/v1/resource/<resource_key>/access

isAuthorized(
    edi_token: The token of the requesting client
    resource_key: The unique resource key of the resource
    permission: The permission level to check ("read", "write", or changePermission")
)

Returns:
  200 OK if the client has access at the specified permission level
  401 Unauthorized if the client does not provide a valid authentication token
  403 Forbidden if client is not authorized to execute method or access resource
  404 If resource is not found
```

## Read Resource

Return the resource associated with a resource key.

```
GET : /auth/v1/resource/<resource_key>

readResource(
    edi_token: The token of the requesting client
    resource_key: The unique resource key of the resource
)

Returns:        
  401 Unauthorized if the client does not provide a valid authentication token
  403 Forbidden if client is not authorized to execute method or access resource
  404 If resource is not found

Permissions:
  authenticated: changePermission
```


## Read Resource Tree

Return the full tree to which the resource belongs. The tree includes the resource itself, it's ancestors, and descendants.

```
GET : /auth/v1/resource-tree/<resource_key>

readResourceTree(
    edi_token: The token of the requesting client
    resource_key: The unique resource key of the resource
)

Returns:        
  401 Unauthorized if the client does not provide a valid authentication token
  403 Forbidden if client is not authorized to execute method or access resource
  404 If resource is not found

Permissions:
  authenticated: changePermission
```


## Update Resource

Update the attributes of a resource.

```
PUT: /auth/v1/resource/<resource_key>

updateResource(
    edi_token: the token of the requesting client
    resource_key: The unique resource key of the resource
    resource_label (optional): The human readable name of the resource
    resource_type (optional): The type of resource
    parent_key (optional): The resource key of the parent
)

Return:
  200 OK if successful
  400 Bad Request if resource is invalid
  401 Unauthorized if the client does not provide a valid authentication token
  403 Forbidden if client is not authorized to execute method or access resource
  404 If resource is not found

Permissions:
  authenticated: changePermission
```

- If `parent_key` is provided, the effect will be a "prune and graft" operation, where the resource, with all its descendants, is moved to a new parent. If `parent_key` is `null`, the resource will be moved up to the root level (or a no-op if the resource is already at the root). If `parent_key` is not provided, the resource will remain a child of its current parent.

## Delete Resource 

Delete a resource.

```
DELETE: /auth/v1/resource/<resource_key>

deleteResource(
    edi_token: The token of the requesting client
    resource_key: The unique resource key of the resource
)

Returns:
  200 OK if successful
  400 Bad Request if resource is invalid
  401 Unauthorized if the client does not provide a valid authentication token
  403 Forbidden if client is not authorized to execute method or access resource
  404 If resource is not found

Permissions:
  authenticated: changePermission
```

- Only a resource without children can be deleted. If a resource has children, this method should be called recursively to delete leaf nodes until there are no more children, after which the resource can be deleted.




