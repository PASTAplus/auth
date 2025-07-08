# Access Control Rule (ACR) Management API

- [Index](index.md) - API Documentation
- [Parameters](parameters.md) - API Parameter Details
- [Profiles](profile.md) - Create and manage user profiles
- [Resources](resource.md) - Create and manage resources
- [Rules](rule.md) - Create and manage the ACRs for resources

This document describes the API for managing permission rules.

## Create Rule

Create an access control rule (ACR) for a resource.

The token profile must be an owner of the resource.

```
POST: /auth/v1/rule

createRule(
    edi_token: the token of the requesting client
    resource_key: the unique resource key of the resource
    principal: the principal of the ACR
    permission: the permission level of the ACR
)

Returns:
  200 OK
  400 Bad Request
  401 Unauthorized
  403 Forbidden

Permissions:
  authenticated: changePermission
```

### Examples

Example request using cURL and JSON:

```shell
curl -X POST https://auth.edirepository.org/auth/v1/rule \
-H "Cookie: edi-token=$(<~/Downloads/token-EDI-<my-token>.jwt)" \
-d '{
  "resource_key": "https://pasta.lternet.edu/package/data/eml/edi/643/4/87c390495ad405e705c09e62ac6f58f0",
  "principal": "EDI-1234567890abcdef1234567890abcdef",
  "permission": "changePermission"
}'
```

Example JSON `200 OK` response:

```json
{
  "method": "createRule",
  "msg": "Access control rule created successfully"
}
```

### Status codes

- `200 OK`
  - A new rule was created

- `400 Bad Request`
  - In addition to possible reasons outlined in [Parameters](parameters.md):
    - A rule already exists on the resource for the principal
    - The resource key does not exist
    - The principal is not a valid EDI-ID
    - The permission is not a valid permission level (must be 'read', 'write', or 'changePermission')

---


## Read Rule

Read the access control rule for principal on a resource.

```
GET: /auth/v1/rule/<resource_key>/<principal_edi_id>

readRule(
    edi_token
    resource_key: The unique resource key of the resource
    principal_edi_id: The EDI-ID of the principal granted access through this rule
)

Returns:
  200 OK if successful
  400 Bad Request if ACR is invalid
  401 Unauthorized if the client does not provide a valid authentication token
  403 Forbidden if client is not authorized to execute method or access ACR
  404 If rule is not found

Permissions:
  authenticated: changePermission
```

## Update Rule

Update the access control rule for a principal on a resource.

- Note: It is an error if the client attempts to modify the `changePermission` permission of a principal if no other principal has `changePermission` permission.

```
PUT: /auth/v1/rule/<resource_key>/<principal>

updateRule(
    edi_token
    resource_key: the unique resource key of the resource
    principal: the principal of the ACR
    permission: the permission of the ACR (may be `None` if DELETE)
)
    
Returns;
  200 OK if successful
  400 Bad Request if ACR is invalid
  401 Unauthorized if the client does not provide a valid authentication token
  403 Forbidden if client is not authorized to execute method or access ACR
  404 If rule is not found
  422 If no `changePermission` would occur

Permissions:
  authenticated: changePermission
```

## Delete Rule

Delete the access control rule for a principal on a resource.

```
DELETE: /auth/v1/resource/<resource_key>/<principal_edi_id>

deleteResource(
    edi_token: the token of the requesting client
    resource_key: the unique resource key of the resource
    principal_edi_id: the principal of the ACR
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

