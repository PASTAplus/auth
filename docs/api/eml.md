# EML API

- [Index](index.md) - API Documentation
- [Parameters](parameters.md) - API Parameter Details
- [Profiles](profile.md) - Manage user profiles
- [Resources](resource.md) - Manage resources
- [Rules](rule.md) - Manage access control rules (ACRs) for the resources
- [EML](eml.md) - Manage EML documents and associated ACRs

This document describes the API for managing permissions via EML documents.

## Add EML Document

Parse a valid EML document, create a corresponding data package resource tree, and add its ACRs to the ACR registry for the resources identified in the EML document. The authentication token subject defines the owner of all associated resources.

Notes: 

- This use case supports the existing PASTA data package upload process. Parsing and extracting ACRs from the EML document will require supporting ACRs in both the main EML document and the additional metadata section. The principal owner of the data package is not currently represented in the existing `access_matrix`. However, this should change for consistency: the principal owner (identified by the authentication token subject) should be added to the ACR registry with the "changePermission" permission. This method should create a data package resource tree.
```
POST: /auth/v1/eml

addEML(
    edi_token: the token of the requesting client
    eml: valid EML document as a string
)

Returns:
    200 OK
    400 Bad Request - EML is invalid or if related resources already exist
    401 Unauthorized
    403 Forbidden

Permissions:
    Caller must be in the Vetted system group
```
