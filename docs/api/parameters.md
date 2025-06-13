# API Parameter Details

- [Index](index.md) - API Documentation
- [Parameters](parameters.md) - API Parameter Details
- [Profiles](profile.md) - Create and manage user profiles
- [Resources](resource.md) - Create and manage resources
- [Rules](rule.md) - Create and manage the ACRs for resources

# Request parameters

While parameters are listed in a generic way in the individual API endpoints, the parameters are passed in specific locations, as outlined here.

## Header Parameters

- `jwt_token`: The authentication token of the requesting client
  - Passed in the request header as `Cookie: jwt_token=<token>`
- `accept`: Set the desired response format
  - When unset, the default response format is JSON (`Accept: application/json`)
  - When set to `application/xml` or `text/xml`, the response will be in XML format
  - When set to `application/json`, the response will be in JSON format
  - Other MIME types are currently not supported and will result in a `400 Bad Request` response

## JSON Body and Query Parameters

For GET requests, the following parameters are passed as query parameters. For POST requests, they are passed as JSON in the request body.

- `idp_uid`: The unique user identifier provided by the IdP
  - E.g., LDAP DN, Google UID, Microsoft UID, GitHub URL, ORCID, email address
  - Examples:
    - **LDAP**: `uid=username,o=EDI,dc=edirepository,dc=org`
    - **Google (old)**: `username@gmail.com`
    - **Google (new)**: `123456789012345678901`
    - **Microsoft**: `AAAAAAAAAAAAAAAAAAAAAxyz`
    - **ORCID**: `https://orcid.org/1234-5678-90AB-CDEF`
    - **GitHub**: `https://github.com/username`

# Response status codes

The following status codes may be returned by the API methods. If a status code is not listed in the method description, it is not applicable to that method. If it is listed, the semantics are as follows, unless otherwise specified in the method description:

- `200 OK`
  - The API call completed successfully
  - The response body will contain JSON or XML with the result of the operation
- `400 Bad Request`
    - The request was invalid and could not be processed
    - The reason will be included in the response body `msg` field
    - Possible reasons include:
        - The body was not well-formed JSON
        - The body JSON had incorrect structure or was missing a required field
        - An unsupported MIME type was specified in the Accept header
- `401 Unauthorized`
    - The client did not provide a valid authentication token
- `403 Forbidden`
    - The client is not authorized to execute method or access resource
- `5xx Internal Server Error`
    - An unexpected error occurred on the server
    - The response body may not be well-formed JSON or XML in this case.

# Examples

Example JSON request body for method that takes only `idp_uid` as a parameter:

```json
{
  "idp_uid": "6789000006297235623708"
}
```

Example JSON response body for `createProfile() -> 200 OK`:

```json
{
  "method": "createProfile",
  "edi_id": "edi-1234567890abcdef1234567890abcdef",
  "msg": "A new profile was created"
}
```

Or as XML:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<result>
    <method>createProfile</method>
    <edi_id>edi-1234567890abcdef1234567890abcdef</edi_id>
    <msg>A new profile was created.</msg>
</result>
```

Example response body for `createProfile() -> 400 Bad Request` when the request body is not well-formed JSON:

```json
{
  "method": "createProfile",
  "msg": "Request body is not well-formed JSON"
}
```
