# Search API

- [Index](index.md) - API Documentation
- [Parameters](parameters.md) - API Parameter Details
- [Profiles](profile.md) - Manage user profiles
- [Resources](resource.md) - Manage resources
- [Rules](rule.md) - Manage the ACRs for resources
- [EML](eml.md) - Manage EML documents and associated ACRs
- [Groups](group.md) - Manage groups and group members
- [Search](search.md) - Search for profiles and groups
- [Token and API key](token.md) - Manage tokens and API keys

## Search Profiles and Groups

Search for EDI profiles and groups based on a provided search string.

- The search is case-insensitive and supports partial matches
- The search string must be at least 3 characters long
- Matches always start at the beginning of each field
- Only a limited number of results are returned. If the expected match is not found, try refining the search string.
- For profiles, the search string is matched against:
  - The full common name (CN)
  - The second part of the common name (family name in Western cultures)
  - Email address
  - Profile EDI-ID ('EDI-' prefix is optional)
- For groups, the search string is matched against:
  - Group name
  - Group description
  - Group EDI-ID ('EDI-' prefix is optional)

```
GET: /auth/v1/profile?s=<search_string>&profiles=<true|false>&groups=<true|false>

searchPrincipals(
  edi_token 
  s (search string, min length: 3)
  profiles (optional, default: true)
  groups (optional, default: true)
)

Returns:
  200 OK
  401 Unauthorized
  403 Forbidden
  404 Not Found

Permissions:
  Caller must be authenticated
```

Example JSON `200 OK` response:

```json
{
  "method": "searchPrincipals",
  "msg": "Profiles and/or groups searched successfully",
  "profiles": [
    {
      "edi_id": "EDI-147dd745c653451d9ef588aeb1d6a188",
      "common_name": "John Smith",
      "email": "john@smith.com",
      "avatar_url": "https://auth.edirepository.org/auth/ui/api/avatar/gen/JS"
    }
  ],
  "groups": [
    {
      "edi_id": "EDI-abcdef1234567890abcdef1234567890",
      "name": "Researchers",
      "description": "Group for all researchers"
    }
  ]
}
```
