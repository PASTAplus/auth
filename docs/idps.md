## PASTA+ Identity Providers (IdPs)

The PASTA+ Identity Providers (IdPs) are the organizations that provide user
authentication services to the PASTA+ Data Repository environment. The following
IdPs are currently supported:

### Environmental Data Initiative (EDI)
EDI manages a local LDAP server that is used to authenticate users. Only EDI administrators
may add a new "vetted" user to the LDAP registry. 

#### Configuration

### Google
Google provides an OAuth2/IdConnect authentication service that is used to authenticate users.
These users may self-register with Google and are therefore not "vetted" by an administrator.
Self-registered users are considered "authenticated" but not "vetted".


#### Configuration
 - User: edirepository@gmail.com
 - Path: https://console.cloud.google.com/apis/credentials/oauthclient
 - Google API Services User Data Policy: https://developers.google.com/terms/api-services-user-data-policy


### ORCID
ORCID provides an OAuth2/IdConnect authentication service that is used to authenticate users.
These users may self-register with Google and are therefore not "vetted" by an administrator.
Self-registered users are considered "authenticated" but not "vetted".

#### Configuration
 - User: mark.servilla@gmail.com
 - Path: https://orcid.org/developer-tools


### GitHub
GitHub provides an OAuth2/IdConnect authentication service that is used to authenticate users.
These users may self-register with Google and are therefore not "vetted" by an administrator.
Self-registered users are considered "authenticated" but not "vetted".

#### Configuration
Oauth configuration for GitHub is maintained through the EDI organization: Settings / Developer Settings /
Oauth Apps.

### Microsoft

#### Configuration
 - User: edirepository@gmail.com
 - Path: https://portal.azure.com/#home