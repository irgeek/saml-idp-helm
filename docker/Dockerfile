FROM node:20-alpine

ARG SAML_IDP_VERSION=1.2.1

WORKDIR /app

RUN apk add --no-cache git \
    && npm install --omit=dev saml-idp@${SAML_IDP_VERSION} \
    && apk del git \
    && chown -R node:node /app

# node:*-alpine already ships a "node" user at uid/gid 1000. Use its numeric
# UID:GID (not the name) so Kubernetes' runAsNonRoot check can verify
# non-root without shelling into the image to resolve /etc/passwd.
USER 1000:1000

EXPOSE 7000

ENTRYPOINT ["node", "node_modules/saml-idp/app.js"]
