# saml-idp-helm

A container image and Helm chart for running [`saml-idp`](https://www.npmjs.com/package/saml-idp) (a test
SAML 2.0 Identity Provider) on Kubernetes, published to GHCR.

- **Image**: `ghcr.io/irgeek/saml-idp-helm/saml-idp`
- **Chart**: `oci://ghcr.io/irgeek/saml-idp-helm/charts/saml-idp`

## Quick start

```console
helm install my-idp oci://ghcr.io/irgeek/saml-idp-helm/charts/saml-idp \
  --set idp.acsUrl=https://sp.example.com/saml/acs \
  --set idp.audience=https://sp.example.com \
  --set certificate.existingSecret.name=my-idp-tls
```

See [`charts/saml-idp/README.md`](charts/saml-idp/README.md) for full chart documentation, including how
to have `cert-manager` issue the signing certificate instead of supplying your own Secret.

## Repository layout

- `docker/` — the `Dockerfile` that packages the `saml-idp` npm CLI into a container image.
- `charts/saml-idp/` — the Helm chart.
- `.github/workflows/ci.yml` — lints the chart and test-builds the image on every pull request.
- `.github/workflows/release.yml` — on pushes to `main` and on `vX.Y.Z` tags, builds/pushes the image and
  packages/pushes the chart to GHCR. Tags publish semantic-versioned releases (`X.Y.Z`, `latest`); pushes
  to `main` publish rolling `edge` builds.

## Local development

```console
helm lint charts/saml-idp
helm template charts/saml-idp \
  --set idp.acsUrl=https://sp.example.com/acs \
  --set idp.audience=https://sp.example.com \
  --set certificate.existingSecret.name=dummy-tls

docker build -f docker/Dockerfile docker
```
