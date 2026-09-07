FROM node:20-alpine

ARG SAML_IDP_VERSION=1.2.1

WORKDIR /app

RUN npm install --omit=dev saml-idp@${SAML_IDP_VERSION} \
    && addgroup -S saml-idp \
    && adduser -S saml-idp -G saml-idp \
    && chown -R saml-idp:saml-idp /app

USER saml-idp

EXPOSE 7000

ENTRYPOINT ["node", "node_modules/saml-idp/app.js"]
