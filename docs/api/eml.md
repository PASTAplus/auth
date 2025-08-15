# EML API

- [Index](index.md) - API Documentation
- [Parameters](parameters.md) - API Parameter Details
- [Profiles](profile.md) - Manage user profiles
- [Resources](resource.md) - Manage resources
- [Rules](rule.md) - Manage access control rules (ACRs) for the resources
- [EML](eml.md) - Manage EML documents and associated ACRs

This document describes the API for managing permissions via EML documents.

## Add EML Document

Parse a valid EML document, create a corresponding data package resource tree, and add its ACRs to the ACR registry for the resources identified in the EML document. The authentication token subject defines the owner, which receives "changePermission" on all associated resources.

The key_prefix sets the prefix for the resource keys for the package root resource and the Metadata branch of the resource tree. E.g., `https://pasta.lternet.edu` (note: no ending slash). For the entities in the Data branch of the resource tree, the full key is read from the `/physical/distribution/online/url` element of each entity.

```
POST: /auth/v1/eml

addEML(
    edi_token
    eml: Valid EML XML document
    key_prefix: Prefix for the package root and Metadata resource keys ()
)

Returns:
    200 OK
    400 Bad Request - EML is invalid or if related resources already exist
    401 Unauthorized
    403 Forbidden

Permissions:
    Caller must be in the Vetted system group
```
