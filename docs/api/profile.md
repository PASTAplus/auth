# User Profile Management API

- [Index](index.md) - API Documentation
- [Parameters](parameters.md) - API Parameter Details
- [Profiles](profile.md) - Create and manage user profiles
- [Resources](resource.md) - Create and manage resources
- [Rules](rule.md) - Create and manage the ACRs for resources

This document describes the API for managing user profiles.

## Create Profile

Create a 'skeleton' EDI profile that can be used in permissions. This method is idempotent, meaning that if a profile already exists for the provided `idp_uid`, it will return the existing profile identifier instead of creating a new one.

If and when a user logs into the profile for the first time, the profile and identity are updated from 'skeleton' to regular with the information provided by the IdP.

```
POST: /auth/v1/profile

createProfile(
  jwt_token
  idp_uid
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
  - A new profile was created or an existing profile was used. The `msg` field in the response body will indicate which.

### Examples

Example request using curl and JSON:

```shell
curl -X POST https://auth.edirepository.org/auth/v1/profile \
-H "Cookie: jwt_token=$(<~/Downloads/token-EDI-<my-token>.jwt)" \
-d '{
  "idp_uid": "uid=username,o=EDI,dc=edirepository,dc=org"
}'
```

Example JSON `200 OK` response:

```json
{
  "method": "createProfile",
  "msg": "A new profile was created"
}
```

---

