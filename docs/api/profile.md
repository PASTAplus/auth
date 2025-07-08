# User Profile Management API

- [Index](index.md) - API Documentation
- [Parameters](parameters.md) - API Parameter Details
- [Profiles](profile.md) - Manage user profiles
- [Resources](resource.md) - Manage resources
- [Rules](rule.md) - Manage access control rules (ACRs) for the resources

This document describes the API for managing user profiles.

## Create Profile

Create a 'skeleton' EDI profile that can be used in permissions. This method is idempotent, meaning that if a profile already exists for the provided `idp_uid`, it will return the existing profile identifier instead of creating a new one.

If and when a user logs into the profile for the first time, the profile and identity are updated from 'skeleton' to regular with the information provided by the IdP.

```
POST: /auth/v1/profile

createProfile(
  edi_token
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
  - A new profile was created or an existing profile was used.
  - Response body:
    - `msg` - A message indicating if a new profile was created or an existing one was used.
    - `edi_id` - EDI-ID of the new or existing profile.

### Examples

Example request using cURL and JSON:

```shell
curl -X POST https://auth.edirepository.org/auth/v1/profile \
-H "Cookie: edi-token=$(<~/Downloads/token-EDI-<my-token>.jwt)" \
-d '{
  "idp_uid": "uid=username,o=EDI,dc=edirepository,dc=org"
}'
```

Example JSON `200 OK` response:

```json
{
  "method": "createProfile",
  "msg": "A new profile was created",
  "edi_id": "EDI-1234567890abcdef1234567890abcdef"
}
```

---

## Read Profile

Return the EDI profile associated with an EDI profile identifier.

When the profile is owned by the requesting user, additional information such as email, avatar URL, and privacy policy acceptance status is included in the response.

```
GET: /auth/v1/profile/<edi_id>

readProfile(
  edi_token 
  edi_id
)

Returns:
    200 OK
    401 Unauthorized
    403 Forbidden
    404 Not Found

Permissions:
  authenticated: changePermission
```

### Status codes

- `200 OK`
  - Always included in response body:
    - `msg` - A message indicating that the profile was retrieved successfully
    - `edi_id` - EDI-ID of the profile (will match the one provided in the request)
    - `common_name` - Common name of the user who owns the profile
  - Included in response body when the profile is owned by the requesting user:
    - `email` - Email address of the user who owns the profile
    - `avatar_url` - URL of the user's avatar image
    - `email_notifications` - Boolean indicating if the user has opted in to receive email notifications
    - `privacy_policy_accepted` - Boolean indicating if the user has accepted the privacy policy
    - `privacy_policy_accepted_date` - Date when the user accepted the privacy policy

Example JSON `200 OK` response, when the profile is owned by the requesting user:

```json
{
  "method": "readProfile",
  "msg": "Profile retrieved successfully",
  "edi_id": "EDI-147dd745c653451d9ef588aeb1d6a188",
  "common_name": "John Smith",
  "email": "john@smith.com",
  "avatar_url": "https://localhost:5443/auth/avatar/gen/JS",
}
```

Example JSON `200 OK` response, when the profile is **not** owned by the requesting user:

```json
{
  "method": "readProfile",
  "msg": "Profile retrieved successfully",
  "edi_id": "EDI-1234567890abcdef1234567890abcdef",
  "common_name": "John Smith"
}
```

---

## Update Profile

Update the attributes of a user profile associated with an EDI profile identifier.

Only profiles owned by the requesting user can be updated. The `common_name` and `email` fields can be modified, but other fields are read-only. If neither `common_name` nor `email` is provided, the profile remains unchanged.

```
PUT: /auth/v1/profile/<edi_id>

updateProfile(
    edi_token: the token of the requesting client
    edi_id: the EDI profile identifier
    common_name (optional): The user's new common name
    email (optional): The user's new preferred email address
)

Returns:
  200 OK if successful
  401 Unauthorized if the client does not provide a valid authentication token
  403 Forbidden if client is not authorized to execute method or access resource
  404 If EDI profile identifier not found

Permissions:
    authenticated: changePermission
```

Example request using cURL and JSON:

```shell

curl -X PUT https://auth.edirepository.org/auth/v1/profile/EDI-1234567890abcdef1234567890abcdef \



---

## Delete Profile

Delete a user profile associated with an EDI profile identifier.

```
DELETE: /auth/v1/profile/<edi_id>

deleteProfile(edi_token, edi_id)
    edi_token: the token of the requesting client
    edi_id: the EDI profile identifier
    return:
        200 OK if successful
        401 Unauthorized if the client does not provide a valid authentication token
        403 Forbidden if client is not authorized to execute method or access resource
        404 If EDI profile identifier not found
    body:
        Empty if 200 OK, error message otherwise
    permissions:
        authenticated: changePermission
```
