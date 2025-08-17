# Group and group membership management API

- [Index](index.md) - API Documentation
- [Parameters](parameters.md) - API Parameter Details
- [Profiles](profile.md) - Create and manage user profiles
- [Resources](resource.md) - Create and manage resources
- [Rules](rule.md) - Create and manage the ACRs for resources
- [EML](eml.md) - Manage EML documents and associated ACRs
- [Groups](group.md) - Manage groups and group members

This document describes the API for managing groups and group members.

## Add User Profile to Group

Add an EDI user profile to a group.

```
POST: /auth/v1/group/<group_edi_id>/<profile_edi_id>

addGroupMember(
  edi_token
  group_edi_id: The EDI-ID of the group to which the user profiles will be added
  profile_edi_id: The EDI-ID of the user profile to add to the group
)

Returns:
  200 OK
  401 Unauthorized
  403 Forbidden
  404 Not Found - If the group or the user profile does not exist. The response body will contain a
    message indicating which EDI-ID was not found.

Permissions:
  The caller must have 'write' permission on the group.
```

- If the profile EDI-ID is already a member of the group, no changes will be made, and the method will return 200 OK, with a message indicating that the profile was already a member of the group.

### Examples

Adding user profile EDI-1234 to group EDI-99cd:

```shell
curl -X POST https://auth.edirepository.org/auth/v1/group/EDI-99cda3eb50ab4699971c99c55c11a15f/EDI-1234567890abcdef1234567890abcdef \
-H "Cookie: edi-token=$(<~/Downloads/token-EDI-<my-token>.jwt)"
```
