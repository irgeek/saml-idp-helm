# saml-idp

A Helm chart for deploying [saml-idp](https://www.npmjs.com/package/saml-idp), a test SAML 2.0 Identity
Provider, to Kubernetes.

## Installing

```console
helm install my-idp oci://ghcr.io/irgeek/saml-idp-helm/charts/saml-idp \
  --set idp.acsUrl=https://sp.example.com/saml/acs \
  --set idp.audience=https://sp.example.com \
  --set certificate.existingSecret.name=my-idp-tls
```

## Signing certificate

`saml-idp` needs an x509 certificate and private key to sign SAML responses. Provide one of:

- **`certificate.existingSecret.name`** — a Secret (e.g. `kubernetes.io/tls`) you already created,
  containing `tls.crt` / `tls.key` (key names configurable via `certificate.existingSecret.certKey` /
  `certificate.existingSecret.keyKey`).
- **`certificate.certManager.enabled=true`** with `certificate.certManager.issuerRef.name` set — the chart
  creates a cert-manager `Certificate` that issues the cert/key into a Secret for you.

If neither is set, `helm install`/`helm template` fails immediately with an explanatory error rather than
deploying a broken pod.

## Fake user profile

The SAML assertion's user profile/attributes are rendered from `config.user` / `config.metadata` into a
`config.js` ConfigMap. Set `config.existingConfigMap` to a ConfigMap name (containing a `config.js` key)
to fully take over instead.

## Values

| Key | Description | Default |
|---|---|---|
| `image.repository` | Container image | `ghcr.io/irgeek/saml-idp-helm/saml-idp` |
| `image.tag` | Image tag | Chart `appVersion` |
| `idp.acsUrl` | SP assertion consumer URL (required) | `""` |
| `idp.audience` | SP audience URI (required) | `""` |
| `idp.issuer` | IdP issuer URI | `urn:example:idp` |
| `idp.sloUrl` | SP single logout URL | `""` |
| `idp.signResponse` | Sign the SAML response | `true` |
| `idp.encryptAssertion` | Encrypt the assertion (requires `idp.encryptionCert`) | `false` |
| `certificate.existingSecret.name` | Pre-existing Secret with the signing cert/key | `""` |
| `certificate.certManager.enabled` | Have cert-manager issue the signing cert/key | `false` |
| `certificate.certManager.issuerRef.name` | cert-manager Issuer/ClusterIssuer name | `""` |
| `config.user` | Fake user profile attributes | see `values.yaml` |
| `config.metadata` | Attribute definitions returned in the assertion | see `values.yaml` |
| `ingress.enabled` | Create an Ingress | `false` |
| `service.type` | Service type | `ClusterIP` |

See [`values.yaml`](values.yaml) for the full set of configurable values, including resources,
`serviceAccount`, `extraEnv`/`extraVolumes`/`extraVolumeMounts`, `nodeSelector`/`tolerations`/`affinity`.
