import datetime
import logging
import pathlib


class Config(object):
    HERE_PATH = pathlib.Path(__file__).parent.resolve()

    # Flask app
    SECRET_KEY = 'flask-app-secret-key'
    DEBUG = True

    # Logging
    LOG_PATH = pathlib.Path('/var/log/pasta')
    LOG_LEVEL = logging.DEBUG
    LOG_DB_QUERIES = False

    # JWT
    JWT_SECRET_KEY = 'jwt-secret-key'
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRATION_DELTA = datetime.timedelta(hours=8)
    JWT_ISSUER = 'https://auth.edirepository.org'
    JWT_AUDIENCE = 'https://auth.edirepository.org'
    JWT_HOSTED_DOMAIN = 'edirepository.org'

    # Filesystem paths
    STATIC_PATH = HERE_PATH / 'static'
    DB_PATH = (HERE_PATH / '../db.sqlite').resolve()
    AVATARS_PATH = HERE_PATH / 'avatars'
    TEMPLATES_PATH = HERE_PATH / 'templates'

    # URLs
    SERVICE_BASE_URL = 'https://localhost:5443/auth'
    # The path under which the auth service is available. Must match settings in the
    # reverse proxy.
    ROOT_PATH = '/auth'
    # For testing ORCID, the entire app must be running from 127.0.0.1. This is because
    # ORCID does not allow localhost as a redirect URI, and because the base URL must
    # match the redirect URI in order for the target cookie to be assigned to the
    # correct domain.
    # SERVICE_BASE_URL = 'https://127.0.0.1:5443'

    API_HOST_URL = 'https://localhost'
    API_PORT = 5443
    API_BASE_URL = f'{API_HOST_URL}:{API_PORT}/api'

    AVATARS_URL = '/avatars'

    # PASTA+ authentication token
    PUBLIC = 'public'
    SYSTEM = 'https://pasta.edirepository.org/authentication'
    VETTED = 'vetted*authenticated'
    AUTHENTICATED = 'authenticated'
    TTL = 8 * 60 * 60 * 1000  # 8 hours

    # Token signing certificate
    PUBLIC_KEY_PATH = '/path/to/public_key.crt'
    PRIVATE_KEY_PATH = '/path/to/private_key.key'

    #
    # UI
    #

    AVATAR_WIDTH, AVATAR_HEIGHT = 200, 200
    AVATAR_FONT_PATH = HERE_PATH / 'assets/NimbusRoman-BoldItalic.otf'
    AVATAR_FONT_HEIGHT = 0.5
    AVATAR_BG_COLOR = (197, 197, 197, 255)
    AVATAR_TEXT_COLOR = (0, 0, 0, 255)

    # Fuzzy search for group member candidates.
    # Maximum number of results that can be returned.
    FUZZ_LIMIT = 100
    # Lowest match score that can be returned (0 is any match, 100 is only exact match).
    FUZZ_CUTOFF = 60

    #
    # Identity Providers
    #

    # LDAP

    # LDAP service to use for each supported domain
    LDAP_DOMAIN_DICT = {
        'o=EDI,dc=edirepository,dc=org': 'ldap.edirepository.org',
    }

    # GitHub OAuth client
    GITHUB_CLIENT_ID = 'github-client-id'
    GITHUB_CLIENT_SECRET = 'github-client-secret'
    # GITHUB_DISCOVERY_URL = 'https://api.github.com'
    GITHUB_AUTH_ENDPOINT = 'https://github.com/login/oauth/authorize'
    GITHUB_TOKEN_ENDPOINT = 'https://github.com/login/oauth/access_token'
    GITHUB_USER_ENDPOINT = 'https://api.github.com/user'
    # GITHUB_LOGOUT_ENDPOINT = 'https://github.com/login/oauth/logout'

    # Google OAuth client
    GOOGLE_CLIENT_ID = 'google-client-id'
    GOOGLE_CLIENT_SECRET = 'google-client-secret'
    GOOGLE_DISCOVERY_URL = (
        'https://accounts.google.com/.well-known/openid-configuration'
    )
    # GOOGLE_LOGOUT_ENDPOINT = 'https://accounts.google.com/Logout'

    # Orcid OAuth client
    ORCID_CLIENT_ID = 'orcid-client-id'
    ORCID_CLIENT_SECRET = 'orcid-client-secret'
    ORCID_DNS = 'https://orcid.org/'
    ORCID_AUTH_ENDPOINT = 'https://orcid.org/oauth/authorize'
    ORCID_TOKEN_ENDPOINT = 'https://orcid.org/oauth/token'

    # Microsoft OAuth client
    MICROSOFT_CLIENT_ID = 'microsoft-client-id'
    MICROSOFT_CLIENT_SECRET = 'microsoft-client-secret'
    MICROSOFT_AUTH_ENDPOINT = (
        'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
    )
    MICROSOFT_TOKEN_ENDPOINT = (
        'https://login.microsoftonline.com/common/oauth2/v2.0/token'
    )
    MICROSOFT_LOGOUT_ENDPOINT = (
        'https://login.microsoftonline.com/common/oauth2/v2.0/logout'
    )

    # Unit and integration test attributes
    # Unit and integration test attributes
    TEST_USER_DN = 'test-user-dn'
    TEST_USER_BAD_O = 'test-user-bad-o'
    TEST_USER_BAD_UID = 'test-user-bad-uid'
    TEST_USER_PW = 'test-user-pw'
    TEST_TOKEN = 'uid=EDI,o=EDI,dc=edirepository,dc=org*https://pasta.edirepository.org/authentication*1558090703946*authenticated'
    TEST_AUTH_TOKEN = 'dWlkPUVESSxvPUVESSxkYz1lZGlyZXBvc2l0b3J5LGRjPW9yZypodHRwczovL3Bhc3RhLmVkaXJlcG9zaXRvcnkub3JnL2F1dGhlbnRpY2F0aW9uKjE1NTgwOTA3MDM5NDYqYXV0aGVudGljYXRlZA==-yUoVTpyVityVkfqOpGSPosJYzndBMdwoUTGB0osuqyCNOouPxRllz/pRklaEWqi+faNLGHh8Dzh7qrtxTLLDs+MpBXudaJIIQep6PNnvEDgasrTvA9KV/vnKsyDnu4VaJnyuoKGRryP6PXlJs8UTXhtGpRf2vnTM/oifeRx0NB3y7aEv3Xn85ogxl0MaeyXJFeQMAAyN9ahYgJUC4jFgCqYlLj/x0PAlXwq2C/AwnjC/XJ2mxEQm1E/RMY9Z9EjHx+dSruXEs3wQiBbnus7BPvJR84zqEjl3EYpYwmYRkLViDHYoGdbegcDfuUfKv4y5Hun+r0ICNt09nBV4wci3TQ=='
