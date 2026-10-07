"""Flask application serving the login picker, SSO endpoints and metadata."""

import base64
import logging
from datetime import UTC, datetime
from pathlib import Path

from flask import Flask, Response, abort, make_response, render_template, request
from lxml import etree
from werkzeug.middleware.proxy_fix import ProxyFix

from saml_idp.authn_request import (
    AuthnRequest,
    AuthnRequestError,
    decode_saml_request,
    parse_authn_request,
)
from saml_idp.certs import CertStatus, SigningCert, load_certs
from saml_idp.config import Config, ConfigStore
from saml_idp.metadata import build_metadata
from saml_idp.saml_response import ResponseParams, build_response


LAST_CERT_COOKIE = "saml_idp_last_cert"
LAST_USER_COOKIE = "saml_idp_last_user"
COOKIE_MAX_AGE = 365 * 24 * 60 * 60
BINDING_POST = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"

logger = logging.getLogger(__name__)


def _base_url(config: Config) -> str:
    return config.base_url or request.host_url.rstrip("/")


def _entity_id(config: Config) -> str:
    return config.entity_id or f"{_base_url(config)}/metadata"


def _sso_url(config: Config) -> str:
    return f"{_base_url(config)}/sso"


def _pretty_xml(xml: bytes) -> str:
    # For display only: re-serializing would invalidate the signatures.
    return etree.tostring(etree.fromstring(xml), pretty_print=True, encoding="unicode")


def _default_cert(certs: list[SigningCert], now: datetime) -> SigningCert:
    return next((c for c in certs if c.status(now) is CertStatus.VALID), certs[0])


def _authn_request_from_request() -> AuthnRequest | None:
    encoded = request.values.get("SAMLRequest")
    if not encoded:
        return None
    try:
        return parse_authn_request(decode_saml_request(encoded))
    except AuthnRequestError as e:
        abort(400, description=f"Invalid SAMLRequest: {e}")


def create_app(config_path: Path, certs_dir: Path) -> Flask:
    store = ConfigStore(config_path)
    certs = load_certs(certs_dir)
    if not certs:
        raise RuntimeError(f"no signing certificates found in {certs_dir}")
    certs_by_name = {c.name: c for c in certs}

    app = Flask(__name__)
    # Trust X-Forwarded-* from the ingress controller so request.host_url
    # reflects the public URL when idp.baseUrl isn't configured.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    def find_cert(name: str) -> SigningCert:
        cert = certs_by_name.get(name)
        if cert is None:
            abort(404, description=f"Unknown certificate {name!r}")
        return cert

    def render_login(authn_request: AuthnRequest | None) -> str:
        config = store.get()
        now = datetime.now(UTC)
        last_cert = request.cookies.get(LAST_CERT_COOKIE)
        if last_cert not in certs_by_name:
            last_cert = _default_cert(certs, now).name
        warnings = []
        if authn_request:
            if authn_request.issuer and authn_request.issuer != config.sp.entity_id:
                warnings.append(
                    f"The request's issuer {authn_request.issuer!r} doesn't match the "
                    f"configured SP entity ID {config.sp.entity_id!r}; the assertion's "
                    "audience will be the configured value."
                )
            if (
                authn_request.acs_url
                and authn_request.acs_url != config.sp.acs_url
                and not config.sp.allow_request_acs_url
            ):
                warnings.append(
                    f"The request asks for ACS URL {authn_request.acs_url!r}, but "
                    "sp.allowRequestAcsUrl is off, so the response goes to the "
                    f"configured {config.sp.acs_url!r}."
                )
            binding = authn_request.protocol_binding
            if binding and binding != BINDING_POST:
                warnings.append(
                    f"The request asks for the {binding} binding; only HTTP-POST "
                    "is supported."
                )
        return render_template(
            "login.html",
            config=config,
            certs=[(c, c.status(now)) for c in certs],
            last_cert=last_cert,
            last_user=request.cookies.get(LAST_USER_COOKIE),
            authn_request=authn_request,
            relay_state=request.values.get("RelayState", ""),
            entity_id=_entity_id(config),
            sso_url=_sso_url(config),
            warnings=warnings,
        )

    @app.get("/healthz")
    def healthz() -> str:
        return "ok"

    @app.get("/")
    def index() -> str:
        return render_login(None)

    @app.route("/sso", methods=["GET", "POST"])
    def sso() -> str:
        authn_request = _authn_request_from_request()
        if authn_request is None:
            abort(400, description="Missing SAMLRequest parameter")
        logger.info(
            "AuthnRequest %s from %s (ACS %s)",
            authn_request.id,
            authn_request.issuer,
            authn_request.acs_url,
        )
        return render_login(authn_request)

    @app.post("/sso/respond")
    def respond() -> Response:
        config = store.get()
        user = config.find_user(request.form.get("user", ""))
        if user is None:
            abort(400, description="Unknown user")
        cert = find_cert(request.form.get("cert", ""))

        acs_url = config.sp.acs_url
        requested_acs_url = request.form.get("acs_url")
        if requested_acs_url and config.sp.allow_request_acs_url:
            acs_url = requested_acs_url

        now = datetime.now(UTC)
        params = ResponseParams(
            idp_entity_id=_entity_id(config),
            sp_entity_id=config.sp.entity_id,
            acs_url=acs_url,
            in_response_to=request.form.get("request_id") or None,
            name_id=user.email,
            attributes=config.attribute_names.values_for(user),
            lifetime=config.assertion_lifetime,
            sign_response=config.sign_response,
            sign_assertion=config.sign_assertion,
        )
        xml = build_response(params, cert, now)
        logger.info(
            "Signing in %s with certificate %s (%s) to %s",
            user.email,
            cert.name,
            cert.status(now),
            acs_url,
        )

        response = make_response(
            render_template(
                "post.html",
                acs_url=acs_url,
                saml_response=base64.b64encode(xml).decode("ascii"),
                relay_state=request.form.get("relay_state", ""),
                inspect="inspect" in request.form,
                xml=_pretty_xml(xml),
                user=user,
                cert=cert,
                cert_status=cert.status(now),
            )
        )
        for name, value in (
            (LAST_CERT_COOKIE, cert.name),
            (LAST_USER_COOKIE, user.email),
        ):
            response.set_cookie(name, value, max_age=COOKIE_MAX_AGE, samesite="Lax")
        return response

    def metadata_response(cert: SigningCert) -> Response:
        config = store.get()
        xml = build_metadata(_entity_id(config), _sso_url(config), cert)
        return Response(xml, mimetype="application/samlmetadata+xml")

    @app.get("/metadata")
    def default_metadata() -> Response:
        return metadata_response(_default_cert(certs, datetime.now(UTC)))

    @app.get("/metadata/<name>")
    def cert_metadata(name: str) -> Response:
        return metadata_response(find_cert(name))

    @app.get("/certs/<name>.pem")
    def cert_pem(name: str) -> Response:
        return Response(
            find_cert(name).pem,
            mimetype="application/x-pem-file",
            headers={"Content-Disposition": f'attachment; filename="{name}.pem"'},
        )

    return app
