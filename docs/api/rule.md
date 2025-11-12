# Access Control Rule (ACR) Management API

- [Index](index.md) - API Documentation
- [Parameters](parameters.md) - API Parameter Details
- [Profiles](profile.md) - Manage user profiles
- [Resources](resource.md) - Manage resources
- [Rules](rule.md) - Manage the ACRs for resources
- [EML](eml.md) - Manage EML documents and associated ACRs
- [Groups](group.md) - Manage groups and group members
- [Search](search.md) - Search for profiles and groups
- [Tokens and API keys](token.md) - Manage tokens and API keys

This document describes the API for managing access control rules.

## Create Rule

Create an access control rule (ACR) for a resource.

The token profile must be an owner (have a `changePermission` ACR) on the resource.

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
    - The permission is not a valid permission level (must be `read`, `write`, or `changePermission`)

---


## Read Rule

Read the access control rule (ACR) for a principal on a resource.

This will return the unique rule for the principal on the resource if it exists.

Note: If this method does not find a matching rule, the principal may still have access to the resource through group memberships or through public or authenticated access rules. To check if a principal has access to a resource, use the `isAuthenticated()` method. 

```
GET: /auth/v1/rule/<resource_key>/<principal_edi_id>

readRule(
  edi_token
  resource_key: The unique resource key of the resource
  principal_edi_id: The EDI-ID of the principal granted access through this rule
)

Returns:
  200 OK
  400 Bad Request - ACR is invalid
  401 Unauthorized
  403 Forbidden
  404 Not Found

Permissions:
  authenticated: changePermission
```

## Update Rule

Update the access control rule (ACR) for a principal on a resource.

```
PUT: /auth/v1/rule/<principal_edi_id>/<resource_key>

: The principal granted access by this ACR
updateRule(
  edi_token
  resource_key: the unique resource key of the resource
  principal_edi_id: The EDI-ID of the principal granted access through this rule
  permission: The permission of the ACR (may be `None` if DELETE)
)
    
Returns;
  200 OK
  400 Bad Request
    - ACR is invalid
    - If the client attempts to remove a `changePermission` ACR from a principal, and no other principal has `changePermission` on the resource, the update is not allowed. This ensures that at least one principal always has the ability to change permissions on the resource.
  401 Unauthorized
  403 Forbidden
  404 Not Found
  422 Unprocessable - No `changePermission` would occur

Permissions:
  authenticated: changePermission
```

## Delete Rule

Delete the access control rule (ACR) for a principal on a resource.

```
DELETE: /auth/v1/resource/<resource_key>/<principal_edi_id>

deleteResource(
  edi_token: the token of the requesting client
  resource_key: the unique resource key of the resource
  principal_edi_id: the principal of the ACR
)

Returns:
  200 OK
  400 Bad Request if resource is invalid
  401 Unauthorized
  403 Forbidden
  404 Not Found

Permissions:
  authenticated: changePermission
```
