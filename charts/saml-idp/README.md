# saml-idp

A Helm chart for deploying a test SAML 2.0 Identity Provider that lets you pick the user and the signing
certificate on every login. See the [repository README](../../README.md) for what the IdP does.

## Installing

```console
helm install my-idp oci://ghcr.io/irgeek/saml-idp-helm/charts/saml-idp -f my-values.yaml
```

with, for example:

```yaml
sp:
  entityId: https://sp.example.com
  acsUrl: https://sp.example.com/saml/acs

users:
  - email: alice@example.com
    firstName: Alice
    lastName: Anderson
  - email: bob@example.com
    firstName: Bob
    lastName: Brown

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: saml-idp.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - hosts: [saml-idp.example.com]
      secretName: saml-idp-tls
```

## Signing certificates

An init container generates four certificates (`valid-1`, `valid-2`, `expired`, `not-yet-valid`) into
an in-memory `emptyDir` each time the pod starts. **A pod restart creates new certificates**, so the
SP has to be given the new certificate or metadata afterwards (`/metadata/<cert>` or
`/certs/<cert>.pem`).

User, SP and attribute changes made with `helm upgrade` only update the ConfigMap. The running pod picks
them up within a minute or so, without restarting, so the certificates are kept.

The chart always runs a single replica with the `Recreate` strategy, because each pod has its own
certificates.

## Base URL and entity ID

The IdP's entity ID defaults to `<baseUrl>/metadata`, and the SSO URL in its metadata is
`<baseUrl>/sso`. `idp.baseUrl` defaults to the first ingress host (`https://` when `ingress.tls` is
set). Without an ingress, set `idp.baseUrl` explicitly. Otherwise the URL is taken from each request,
and the entity ID would change between, say, a port-forward and a cluster-internal URL.

## Values

| Key | Description | Default |
|---|---|---|
| `sp.entityId` | SP entity ID, used as the audience (required) | `""` |
| `sp.acsUrl` | SP assertion consumer service URL (required) | `""` |
| `sp.allowRequestAcsUrl` | Honour the ACS URL in an AuthnRequest | `false` |
| `users` | Users offered on the login page (`email`, `firstName`, `lastName`) | Two example users |
| `attributeNames.email` | Attribute name for the email (`""` to omit) | `email` |
| `attributeNames.firstName` | Attribute name for the first name (`""` to omit) | `first_name` |
| `attributeNames.lastName` | Attribute name for the last name (`""` to omit) | `last_name` |
| `idp.baseUrl` | Public URL of the IdP | First ingress host |
| `idp.entityId` | IdP entity ID | `<baseUrl>/metadata` |
| `idp.signResponse` | Sign the Response element | `true` |
| `idp.signAssertion` | Sign the Assertion element | `true` |
| `idp.assertionLifetimeSeconds` | Assertion validity in seconds | `300` |
| `image.repository` | Container image | `ghcr.io/irgeek/saml-idp-helm/saml-idp` |
| `image.tag` | Image tag | Chart `appVersion` |
| `ingress.enabled` | Create an Ingress | `false` |
| `service.type` | Service type | `ClusterIP` |
| `service.port` | Service port | `80` |

See [`values.yaml`](values.yaml) for the full set of configurable values, including resources,
`serviceAccount`, `extraEnv`/`extraVolumes`/`extraVolumeMounts`, `nodeSelector`/`tolerations`/`affinity`.
