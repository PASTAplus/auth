# Group and group membership management API

- [Index](index.md) - API Documentation
- [Parameters](parameters.md) - API Parameter Details
- [Profiles](profile.md) - Manage user profiles
- [Resources](resource.md) - Manage resources
- [Rules](rule.md) - Manage the ACRs for resources
- [EML](eml.md) - Manage EML documents and associated ACRs
- [Groups](group.md) - Manage groups and group members
- [Search](search.md) - Search for profiles and groups
- [Token and API key](token.md) - Manage tokens and API keys

This document describes the API for managing groups and group members.


### Create Group

Create a new group of EDI user profiles.

```
POST: /auth/v1/group

createGroup(
    edi_token
    title: The title of the group
    description: The description of the group
)

Returns:
    200 OK
    401 Unauthorized
    403 Forbidden

Body:
    Group's EDI-ID if 200 OK, error message otherwise

Permissions:
    Caller must be in the Vetted system group
```

## Read Group

Retrieve the title, description and member list of a group.

```
GET: /auth/v1/group/<group_edi_id>

readGroup(
    edi_token
    group_edi_id: the group EDI-ID
)

Returns:
    200 OK
    401 Unauthorized
    403 Forbidden
    404 Not Found - The group does not exist

Permissions:
    The caller must have 'read' permission on the group.
```

## Update Group Details

Modify the title and/or description of a group.

```
PUT: /auth/v1/group/<group_edi_id>

updateGroup(
    edi_token
    title: The title of the group (optional)
    description: The description of the group (optional)
)

Returns:
    200 OK if successful
    401 Unauthorized if the client does not provide a valid authentication token
    403 Forbidden if client is not authorized to execute method or access resource
    404 If the group does not exist

    
    body:
        Empty if 200 OK, error message otherwise

Permissions:
  The caller must have 'write' permission on the group.
```

## Delete Group

Delete an EDI group.

```
DELETE: /auth/v1/group/<group_edi_id>

deleteGroup(edi_token, group_name)
    edi_token: the token of the requesting client
    group_edi_id: the group EDI-ID
    return:
        200 OK if successful
        401 Unauthorized if the client does not provide a valid authentication token
        403 Forbidden if client is not authorized to execute method or access resource
        404 If the group does not exist
    body:
        Empty if 200 OK, error message otherwise

Permissions:
  The caller must have 'write' permission on the group.
```

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

## Remove a User Profile from a Group

Remove an EDI user profile from a group.

```
DELETE: /auth/v1/group/<group_edi_id>/<profile_edi_id>

removeGroupMember(edi_token, group_edi_id, profile_edi_id)
    edi_token: the token of the requesting client
    group_edi_id: the group EDI-ID
    profile_edi_id: the profile EDI-ID to remove from the group
    return:
        200 OK if successful
        401 Unauthorized if the client does not provide a valid authentication token
        403 Forbidden if client is not authorized to execute method or access resource
        404 If the group does not exist or if the user does not exist
    body:
        Empty if 200 OK, error message otherwise

Permissions:
  The caller must have 'write' permission on the group.
```

