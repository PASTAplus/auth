# auth

PASTA+ Authentication Service ('Auth')

Multiverse authentication service for the PASTA+ Data Repository environment.


## Authentication

- EDI services support signing in via LDAP and via selected 3rd party identity providers (IdPs) using OAuth2 / OpenID Connect (OIDC)
- LDAP accounts are managed by EDI and provide membership in the `vetted` group
- All users that sign in (via LDAP or OAuth2) become members of the `authenticated` group

### Supported Identity Providers (IdPs)

### EDI LDAP (Lightweight Directory Access Protocol)

- LDAP accounts are managed by EDI and provide membership in the `vetted` group, which provides elevated privileges for users publishing packages on EDI

#### Configuration

- TODO


### Google

- Google's OAuth2 service is part of Google Cloud and accessed via Google Cloud Console

#### Configuration

- User: edirepository@gmail.com

- EDI app location:
  - https://console.cloud.google.com > `APIs & Services` > `Credentials` > `OAuth 2.0 Client IDs` > `EDI Authentication`
  - Currently: https://console.cloud.google.com/apis/credentials?authuser=2&project=edi-authentication

#### Notes

- Google API Services User Data Policy: https://developers.google.com/terms/api-services-user-data-policy

### ORCID

#### Configuration

- User: mark.servilla@gmail.com
- EDI app location:
  - https://orcid.org > `User name (upper right)` > `Developer tools`
  - Currently: https://orcid.org/developer-tools


### GitHub

#### Configuration

- Oauth configuration for GitHub is maintained through the EDI organization (`EDIorg`)
- EDI App location:
  - https://github.com/EDIorg > `Settings` > `Developer settings` > `OAuth Apps`
  - Currently: https://github.com/organizations/EDIorg/settings/applications


### Microsoft

- Microsoft's OAuth2 service is part of Microsoft Entra ID.

#### Configuration

- User: admin@edirepository.onmicrosoft.com
- Email: edirepository@gmail.com
- EDI app location:
  - https://entra.microsoft.com/#home > `App registrations` > `View all applications` > `Select the EDI app`
  - Currently: https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/~/Authentication/appId/9b0f517e-4766-4176-897c-0e39bcd1f662

#### Notes

  - To edit the Redirect URIs, select `Redirect URIs` under `Essentials`
  - The EDI app is configured to support accounts in any organizational directory (any Microsoft Entra ID tenant or multitenant), and personal Microsoft accounts (e.g., Skype, Xbox)
  - We do not currently use the Logout URI
  - Select the tokens you would like to be issued by the authorization endpoint:
    - Access tokens (used for implicit flows): Y
    - ID tokens (used for implicit and hybrid flows): Y
    - Live SDK support: N
    - Allow public client flows: N


### redirect_uri

The `redirect_uri` in OAuth2 is always a URL provided by the client. After successful sign-in, the IdP redirects to this URL, appending the user's security context as query parameters.

To prevent spoofing, the `redirect_uri` must exactly match a registered value at the IdP. Multiple `redirect_uri`s can be registered to support different instances of the same OAuth2 application. For Auth, the `redirect_uri` follows this format:

`https://<HOST><:PORT>/auth/callback/<IDP_NAME>`
 
Since we currently have public production and test instances of Auth, and also run Auth locally under port 5443 for development, these are the `redirect_uri`s that we need to be preconfigured at each IdP.

#### GitHub

- https://auth.edirepository.org/auth/callback/github
- https://auth-d.edirepository.org/auth/callback/github
- https://localhost:5443/callback/github

#### Google

- https://auth.edirepository.org/auth/callback/google
- https://auth-d.edirepository.org/auth/callback/google
- https://localhost:5443/callback/google

#### Microsoft

- https://auth.edirepository.org/auth/callback/microsoft
- https://auth-d.edirepository.org/auth/callback/microsoft
- https://localhost:5443/callback/microsoft

#### ORCID

- https://auth.edirepository.org/auth/callback/orcid
- https://auth-d.edirepository.org/auth/callback/orcid
- https://localhost:5443/callback/orcid


## Conda

### Managing the Conda environment in a production environment

Start and stop the auth service as root:

```shell
# systemctl start auth.service
# systemctl stop auth.service
```

Remove and rebuild the auth venv:

```shell
conda env remove --name auth
conda env create --file environment-min.yml
```

Update the auth venv in place:

```shell
conda env update --file environment-min.yml --prune
```

Activate and deactivate the auth venv:

```shell
conda activate auth
conda deactivate
```

### Managing the Conda environment in a development environment

Update the environment.yml:

```shell
conda env export --no-builds > environment.yml
```
Update Conda itself:

```shell
conda update --name base conda
```

Update all packages in environment:

```shell
conda update --all
```

Create or update the `requirements.txt` file (for use by GitHub Dependabot, and for pip based manual installs):

```shell
pip list --format freeze > requirements.txt
```

### Procedure for updating the Conda environment and all dependencies

```shell
conda update -n base -c conda-forge conda
conda activate auth
conda update --all
conda env export --no-builds > environment.yml
pip list --format freeze > requirements.txt
```

### If Conda base won't update to latest version, try:

```shell
conda install conda==<version>
``` 

or

```shell
conda update -n base -c defaults conda --repodata-fn=repodata.json
```
