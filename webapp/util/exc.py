import db.models.permission

class AuthError(Exception):
    """Exceptions in IAM"""
    pass

class InvalidRequestError(AuthError):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


# Resource

class ResourceDoesNotExistError(AuthError):
    def __init__(self, key):
        self.key = key
        self.message = f'Resource with key "{key}" does not exist.'
        super().__init__(self.message)

class ResourceIdDoesNotExistError(AuthError):
    def __init__(self, resource_id):
        self.resource_id = resource_id
        self.message = f'Resource with ID {resource_id} does not exist.'
        super().__init__(self.message)


class ResourceAlreadyExistsError(AuthError):
    def __init__(self, key):
        self.key = key
        self.message = f'Resource with key "{key}" already exists.'
        super().__init__(self.message)


class ResourcePermissionDeniedError(AuthError):
    def __init__(self, edi_id, key, permission_level):
        self.key = key
        self.permission_level = permission_level
        self.message = (
            f'Profile "{edi_id}" does not have '
            f'"{db.models.permission.permission_level_enum_to_string(permission_level)}" '
            f'permission on resource with key "{key}"'
        )
        super().__init__(self.message)

# EML

class EmlError(AuthError):
    """Class for exceptions related to EML operations."""
    pass
