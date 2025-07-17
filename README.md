# Auth

EDI Authentication and Authorization Service

Multiverse authentication service for the PASTA+ Data Repository environment.

- EDI services support signing in via LDAP and via selected 3rd party identity providers (IdPs) using OAuth2 / OpenID Connect (OIDC)
- LDAP accounts are managed by EDI and provide membership in the `vetted` group
- All users that sign in (via LDAP or OAuth2) become members of the `authenticated` group

## API

Auth provides a REST API for managing user profiles, identities, and access control rules (ACRs) for data packages and other resources in the EDI Data Repository. The API is designed to be used by client applications to create and manage user profiles, and manage access to resources.

- [Index](./docs/api/index.md) - API Documentation
- [Parameters](./docs/api/parameters.md) - API Parameter Details
- [Profiles](./docs/api/profile.md) - Create and manage user profiles
- [Resources](./docs/api/resource.md) - Create and manage resources
- [Rules](./docs/api/rule.md) - Create and manage access control rules (ACRs) for the resources

## Strategy for dealing with Google emails historically used as identifiers

This procedure describes how we'll handle the IdP UID (stored in Identity.idp_uid) in a way that lets us migrate away from using Google emails as identifiers, while still allowing users to log in with their Google accounts, and moving to using Google's OAuth2 UID as the unique identifier for users.

- When a new profile is created through the API:
  - Always use whatever unique user identifier string provided by the client, as the IdP UID
  - If the unique string already exists in the Identity.idp_uid field:
    - The existing profile is returned
  - If not:
    - If the unique string is in the Identity.email field:
      - The user profile already exists for someone who logs in through Google
      - The existing profile is returned
    - If not:
      - Create the new identity record with the IdP UID and enter it into the Identity.idp_uid field; create new profile and return profile identifier

- When someone logs in with an IdP other than Google:
  - Follow regular logic, which is to create an identity and profile if one doesn't exist, and then log in the user.
- When someone logs in with Google as their IdP:
  - If an identity exists under the Google IdP UID in the Identity.idp_uid field:
    - Log the user in as normal.
  - If not:
    - If the Google IdP email matches an Identity.idp_uid:
      - Set the new Google IdP UID in Identity.idp_uid
      - Set all other fields
      - Log the user in as normal
    - If not:
      - Create a new identity and profile using the Google IdP UID
      - Set all other fields
      - Log the user into the new profile

## Supported Identity Providers (IdPs)

### EDI LDAP (Lightweight Directory Access Protocol)

- LDAP accounts are managed by EDI and provide membership in the `vetted` group, which provides elevated privileges for users publishing packages on EDI

### Configuration

- TODO


## Google

- Google's OAuth2 service is part of Google Cloud and accessed via Google Cloud Console

### Configuration

- User: edirepository@gmail.com

- EDI app location:
  - https://console.cloud.google.com > `APIs & Services` > `Credentials` > `OAuth 2.0 Client IDs` > `EDI Authentication`
  - Currently: https://console.cloud.google.com/apis/credentials?authuser=2&project=edi-authentication

### Notes

- Google API Services User Data Policy: https://developers.google.com/terms/api-services-user-data-policy

## ORCID

### Configuration

- User: mark.servilla@gmail.com
- EDI app location:
  - https://orcid.org > `User name (upper right)` > `Developer tools`
  - Currently: https://orcid.org/developer-tools


## GitHub

### Configuration

- Oauth configuration for GitHub is maintained through the EDI organization (`EDIorg`)
- EDI App location:
  - https://github.com/EDIorg > `Settings` > `Developer settings` > `OAuth Apps`
  - Currently: https://github.com/organizations/EDIorg/settings/applications


## Microsoft

- Microsoft's OAuth2 service is part of Microsoft Entra ID.

### Configuration

- User: admin@edirepository.onmicrosoft.com
- Email: edirepository@gmail.com
- EDI app location:
  - https://entra.microsoft.com/#home > `App registrations` > `View all applications` > `Select the EDI app`
  - Currently: https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/~/Authentication/appId/9b0f517e-4766-4176-897c-0e39bcd1f662

### Notes

  - To edit the Redirect URIs, select `Redirect URIs` under `Essentials`
  - The EDI app is configured to support accounts in any organizational directory (any Microsoft Entra ID tenant or multitenant), and personal Microsoft accounts (e.g., Skype, Xbox)
  - We do not currently use the Logout URI
  - Select the tokens you would like to be issued by the authorization endpoint:
    - Access tokens (used for implicit flows): Y
    - ID tokens (used for implicit and hybrid flows): Y
    - Live SDK support: N
    - Allow public client flows: N


## redirect_uri

The `redirect_uri` in OAuth2 is always a URL provided by the client. After successful sign-in, the IdP redirects to this URL, appending the user's security context as query parameters.

To prevent spoofing, the `redirect_uri` must exactly match a registered value at the IdP. Multiple `redirect_uri`s can be registered to support different instances of the same OAuth2 application. For Auth, the `redirect_uri` follows this format:

`https://<HOST><:PORT>/auth/callback/<IDP_NAME>`
 
Since we currently have public production and test instances of Auth, and also run Auth locally under port 5443 for development, these are the `redirect_uri`s that we need to be preconfigured at each IdP.

### GitHub

- https://auth.edirepository.org/auth/callback/github
- https://auth-d.edirepository.org/auth/callback/github
- https://localhost:5443/auth/callback/github

### Google

- https://auth.edirepository.org/auth/callback/google
- https://auth-d.edirepository.org/auth/callback/google
- https://localhost:5443/auth/callback/google

### Microsoft

- https://auth.edirepository.org/auth/callback/microsoft
- https://auth-d.edirepository.org/auth/callback/microsoft
- https://localhost:5443/auth/callback/microsoft

### ORCID

- https://auth.edirepository.org/auth/callback/orcid
- https://auth-d.edirepository.org/auth/callback/orcid
- https://127.0.0.1:5443/auth/callback/orcid

Note: ORCID does not support `localhost` in the `redirect_uri`, so we use `127.0.1.1`. However, this conflicts with
requirement for `localhost` by other IdPs, so can only be used for testing ORCID in development. To test ORCID in
development, also set `127.0.0.1` in Config.SERVICE_BASE_URL.
```

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

## Setting up a trusted CA and SSL certificate for local development

To avoid browser warnings about untrusted certificates, we create a self-signed CA certificate and use it to sign a certificate for the local development server.

Browsers do not use the system CA store, so the CA certificate must be added to the browser's trust store. For Chrome, go to `chrome://settings/certificates` and import the CA certificate in the `Authorities` tab.

Brief instructions for creating the CA, and server certificates, and installing them to the system CA store. You will be prompted for a new password for the CA key, and for the same password again when signing the local certificate. There's no need to remember the password after that, unless you plan on signing more certs with the same CA:  

```shell
openssl genpkey -algorithm RSA -out ca.key -aes256
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -out ca.crt -subj "/CN=My Local CA"
openssl genpkey -algorithm RSA -out localhost.key
openssl req -new -key localhost.key -out localhost.csr -subj "/CN=localhost"

cat > localhost.ext <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
EOF

openssl x509 -req -in localhost.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out localhost.crt -days 3650 -sha256 -extfile localhost.ext

sudo cp localhost.crt /etc/ssl/certs/
sudo cp localhost.key /etc/ssl/private/
sudo cp ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

## Chromium DevTools integration

Chromium DevTools workfolders allow developers to work with local files directly in the browser. Integration can be set up in DevTools by adding the project root as a workspace folder. This can also be automated by serving a well-known directory containing a configuration file that DevTools recognizes. As seen from the browser, the directory structure should look like this:

`/.well-known/appspecific/com.chrome.devtools.json`

Example `com.chrome.devtools.json`:

```json
{
  "workspace": {
    "root": "/Users/foobar/Projects/my-awesome-web-project",
    "uuid": "53b029bb-c989-4dca-969b-835fecec3717"
  }
}
```

For details, see:

https://chromium.googlesource.com/devtools/devtools-frontend/+/main/docs/ecosystem/automatic_workspace_folders.md


## Export Postgres DB to another server

Export:

```bash
sudo -su postgres pg_dump -U auth -h localhost auth > /tmp/auth-dump.sql
```

Import:

```bash
sudo -su postgres
psql -U auth -h localhost -c 'drop database if exists auth;'
psql -U auth -h localhost -c 'create database auth;'
psql -U auth -h localhost -c 'alter database auth owner to auth;'
psql -U auth -h localhost auth < /tmp/auth-dump.sql
```
