# Token and API key API

- [Index](index.md) - API Documentation
- [Parameters](parameters.md) - API Parameter Details
- [Profiles](profile.md) - Manage user profiles
- [Resources](resource.md) - Manage resources
- [Rules](rule.md) - Manage the ACRs for resources
- [EML](eml.md) - Manage EML documents and associated ACRs
- [Groups](group.md) - Manage groups and group members
- [Search](search.md) - Search for profiles and groups
- [Token and API key](token.md) - Manage tokens and API keys

## refreshToken

Validate and refresh PASTA and EDI authentication tokens.
- A refreshed token matches the original token but has a new TTL.
- We consider the EDI token to be 'authoritative', so we refresh the pasta-token even if it has
expired, as long as the EDI token has not.
- This method is optimized for high traffic. It works directly with the tokens and does not
query the database, LDAP, or the OAuth2 IdPs.

## 