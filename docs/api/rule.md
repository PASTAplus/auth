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
    jwt_token: the token of the requesting client
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

Example request using curl and JSON:

```shell
curl -X POST https://auth.edirepository.org/auth/v1/rule \
-H "Cookie: jwt_token=$(<myjwt.txt)" \
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

## Update Rule


- Note: It is an error if the client attempts to modify the `changePermission` permission of a principal if no other principal has `changePermission` permission.


