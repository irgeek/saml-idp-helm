# saml-idp-helm

A test SAML 2.0 Identity Provider for exercising an SP's SSO integration, packaged as a container image
and Helm chart and published to GHCR.

- **Image**: `ghcr.io/irgeek/saml-idp-helm/saml-idp`
- **Chart**: `oci://ghcr.io/irgeek/saml-idp-helm/charts/saml-idp`

## What it does

- **Pick a user with one click.** Users (email, first and last name) are defined in config. Each login
  sends the email as the `emailAddress` NameID, plus `email`, `first_name` and `last_name` attributes
  (the names are configurable).
- **Pick the signing certificate per login.** Four certificates are generated at startup:

  | Name | Validity |
  |---|---|
  | `valid-1` | now → +1 year |
  | `valid-2` | now → +1 year |
  | `expired` | −1 year → yesterday |
  | `not-yet-valid` | +1 year → +2 years |

  The IdP signs with whichever one you choose, even the expired or not-yet-valid one, so you can check
  that the SP rejects them.
- **SP- and IdP-initiated login.** An AuthnRequest sent to `/sso` (HTTP-Redirect or HTTP-POST binding)
  lands on a page where you pick the user and certificate. That page is also the home page for
  IdP-initiated login. Your last choices are remembered in cookies, and the last user's button is
  focused, so pressing Enter repeats the last login.
- **Inspect before sending.** Tick "Show the SAML response" to see the signed XML before it's posted to
  the SP.

Responses are posted to the SP using the HTTP-POST binding. Single logout and assertion encryption are
not supported.

### Endpoints

| Path | Purpose |
|---|---|
| `/` | Login page for IdP-initiated login |
| `/sso` | SSO endpoint for SP-initiated login (`GET` or `POST`) |
| `/metadata` | IdP metadata using the first valid certificate |
| `/metadata/<cert>` | IdP metadata using a specific certificate |
| `/certs/<cert>.pem` | A certificate in PEM format |
| `/healthz` | Health check |

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/) to run it locally
- Helm 3 and a Kubernetes cluster to deploy it

## Running locally

```console
uv run saml-idp-gencerts ./certs
SAML_IDP_CONFIG=config.json SAML_IDP_CERTS_DIR=./certs uv run saml-idp --port 8080
```

Or install the commands with `uv tool install .`.

A minimal `config.json`:

```json
{
  "sp": {
    "entityId": "https://sp.example.com",
    "acsUrl": "https://sp.example.com/saml/acs"
  },
  "users": [
    {"email": "alice@example.com", "firstName": "Alice", "lastName": "Anderson"},
    {"email": "bob@example.com", "firstName": "Bob", "lastName": "Brown"}
  ]
}
```

Optional keys:

| Key | Description | Default |
|---|---|---|
| `baseUrl` | Public URL of the IdP, used for the entity ID and the SSO URL in the metadata | The URL of each request |
| `entityId` | IdP entity ID | `<baseUrl>/metadata` |
| `sp.allowRequestAcsUrl` | Use the ACS URL from an AuthnRequest instead of `sp.acsUrl` | `false` |
| `signResponse` | Sign the Response element | `true` |
| `signAssertion` | Sign the Assertion element | `true` |
| `assertionLifetimeSeconds` | Assertion validity | `300` |
| `attributeNames` | Attribute names for `email`, `firstName`, `lastName` (`""` omits one) | `email`, `first_name`, `last_name` |

The config file is reloaded whenever it changes. If an edited file is invalid, the error is logged and
the previous config stays in use.

### Environment variables

| Variable | Description | Default |
|---|---|---|
| `SAML_IDP_CONFIG` | Path to the JSON config file | `/etc/saml-idp/config.json` |
| `SAML_IDP_CERTS_DIR` | Directory of `<name>.crt`/`<name>.key` pairs to sign with | `/var/run/saml-idp/certs` |

Any extra RSA `<name>.crt`/`<name>.key` pairs in the certificates directory are offered too.

### CLI options

`saml-idp`:

| Option | Description | Default |
|---|---|---|
| `--host` | Address to listen on | `0.0.0.0` |
| `--port` | Port to listen on | `8080` |

`saml-idp-gencerts DIRECTORY` writes the four certificates and keys into `DIRECTORY`, creating it if
needed and overwriting any existing files.

### Exit status

Both commands exit `0` on success. They exit non-zero with an `Error: ...` message if the config is
invalid or missing, if no certificates are found, or if the certificates can't be written.

## Deploying with Helm

```console
helm install my-idp oci://ghcr.io/irgeek/saml-idp-helm/charts/saml-idp \
  --set sp.entityId=https://sp.example.com \
  --set sp.acsUrl=https://sp.example.com/saml/acs
```

See [`charts/saml-idp/README.md`](charts/saml-idp/README.md) for the chart's values.

## Repository layout

- `src/saml_idp/`: the IdP (a Flask app served by waitress).
- `Dockerfile`: the container image.
- `charts/saml-idp/`: the Helm chart.
- `.github/workflows/ci.yml`: lints the Python code and chart, and test-builds the image on every pull
  request.
- `.github/workflows/release.yml`: on pushes to `main` and on `vX.Y.Z` tags, builds and pushes the image
  and packages and pushes the chart to GHCR. Tags publish semantic-versioned releases (`X.Y.Z`,
  `latest`); pushes to `main` publish rolling `edge` builds.

## Development

```console
uv run ruff format && uv run ruff check --fix
helm lint charts/saml-idp
helm template charts/saml-idp \
  --set sp.entityId=https://sp.example.com \
  --set sp.acsUrl=https://sp.example.com/acs
docker build .
```
