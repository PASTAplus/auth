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
- We consider the EDI token to be 'authoritative', so we refresh the pasta-token even if it has expired, as long as the EDI token has not.
- This method is optimized for high traffic. It works directly with the tokens and does not query the database, LDAP, or the OAuth2 IdPs.

```
POST: /auth/v1/token/refresh

refreshToken(
  pasta_token
  edi_token
)

Returns:
  200 OK
  400 Bad Request
  401 Unauthorized
  403 Forbidden
  
Permissions:
  Both a valid pasta_token and edi_token are required to call this method.
```

### Examples

Example request using cURL and JSON:

```shell
curl -X POST https://auth.edirepository.org/auth/v1/key \
-d '{
  "pasta-token": "uid=EDI,o=EDI,dc=edirepository...",
  "edi-token": "eyJhbGciOiJFUzI1NiIsInR5cCI6I...",
}'
```

Example JSON `200 OK` response:

```json
{
  "msg": "PASTA and EDI tokens refreshed successfully",
  "pasta-token": "uid=EDI,o=EDI,dc=edirepository...",
  "edi-token": "eyJhbGciOiJFUzI1NiIsInR5cCI6I...",
  "method": "getTokenByKey"
}
```


## getTokenByKey

Retrieve an authentication token using an API key.

```
POST: /auth/v1/key

getTokenByKey(
  key
)

Returns:
  200 OK
  400 Bad Request
  401 Unauthorized
  403 Forbidden
  
Permissions:
  No permissions are required to call this method.
```

### Status codes

- `200 OK`
  - The key was valid and a token has been returned.
  - Response body:
    - `msg` - A message indicating that the token was created successfully.
    - `edi-token` - The new token.

### Examples

Example request using cURL and JSON:

```shell
curl -X POST https://auth.edirepository.org/auth/v1/key \
-d '{
  "key": "R9arQwYMFqdgVVYt7jqcsxfyPyU"
}'
```

Example JSON `200 OK` response:

```json
{
  "msg": "Token created successfully",
  "edi-token": "eyJhbGciOiJFUzI1NiIsInR5cCI6I...",
  "method": "getTokenByKey"
}
```
