"""Construction and signing of SAML 2.0 Responses."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from lxml import etree
from signxml import XMLSigner
from signxml.algorithms import (
    CanonicalizationMethod,
    DigestAlgorithm,
    SignatureConstructionMethod,
    SignatureMethod,
)

from saml_idp.certs import SigningCert


SAMLP_NS = "urn:oasis:names:tc:SAML:2.0:protocol"
SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
XS_NS = "http://www.w3.org/2001/XMLSchema"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

NAMEID_FORMAT_EMAIL = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
ATTRNAME_FORMAT_BASIC = "urn:oasis:names:tc:SAML:2.0:attrname-format:basic"
STATUS_SUCCESS = "urn:oasis:names:tc:SAML:2.0:status:Success"
CM_BEARER = "urn:oasis:names:tc:SAML:2.0:cm:bearer"
AUTHN_CONTEXT_PASSWORD_PROTECTED = (
    "urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"
)
# Allow for clock skew between the IdP and SP when setting NotBefore.
NOT_BEFORE_SKEW = timedelta(minutes=1)


@dataclass(frozen=True)
class ResponseParams:
    idp_entity_id: str
    sp_entity_id: str
    acs_url: str
    in_response_to: str | None
    name_id: str
    attributes: dict[str, str]
    lifetime: timedelta
    sign_response: bool
    sign_assertion: bool


def _new_id() -> str:
    # IDs must be xs:NCName, so they can't start with a digit.
    return f"_{uuid.uuid4().hex}"


def _instant(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sub(
    parent: etree._Element, ns: str, tag: str, text: str | None = None, **attrs: str
) -> etree._Element:
    element = etree.SubElement(parent, f"{{{ns}}}{tag}", attrs)
    if text is not None:
        element.text = text
    return element


def _signature_placeholder(parent: etree._Element) -> None:
    # signxml replaces this with the real signature, which the SAML schema
    # requires immediately after <saml:Issuer>.
    etree.SubElement(
        parent, f"{{{DS_NS}}}Signature", Id="placeholder", nsmap={"ds": DS_NS}
    )


def _sign(element: etree._Element, cert: SigningCert) -> etree._Element:
    signer = XMLSigner(
        method=SignatureConstructionMethod.enveloped,
        signature_algorithm=SignatureMethod.RSA_SHA256,
        digest_algorithm=DigestAlgorithm.SHA256,
        c14n_algorithm=CanonicalizationMethod.EXCLUSIVE_XML_CANONICALIZATION_1_0,
    )
    return signer.sign(
        element,
        key=cert.key,
        cert=[cert.cert],
        reference_uri=element.get("ID"),
        id_attribute="ID",
    )


def _build_assertion(
    params: ResponseParams, cert: SigningCert, now: datetime
) -> etree._Element:
    expires = _instant(now + params.lifetime)
    assertion = etree.Element(
        f"{{{SAML_NS}}}Assertion",
        {"ID": _new_id(), "Version": "2.0", "IssueInstant": _instant(now)},
        nsmap={"saml": SAML_NS, "xs": XS_NS, "xsi": XSI_NS},
    )
    _sub(assertion, SAML_NS, "Issuer", params.idp_entity_id)
    if params.sign_assertion:
        _signature_placeholder(assertion)

    subject = _sub(assertion, SAML_NS, "Subject")
    _sub(subject, SAML_NS, "NameID", params.name_id, Format=NAMEID_FORMAT_EMAIL)
    confirmation = _sub(subject, SAML_NS, "SubjectConfirmation", Method=CM_BEARER)
    confirmation_data = _sub(
        confirmation,
        SAML_NS,
        "SubjectConfirmationData",
        NotOnOrAfter=expires,
        Recipient=params.acs_url,
    )
    if params.in_response_to:
        confirmation_data.set("InResponseTo", params.in_response_to)

    conditions = _sub(
        assertion,
        SAML_NS,
        "Conditions",
        NotBefore=_instant(now - NOT_BEFORE_SKEW),
        NotOnOrAfter=expires,
    )
    restriction = _sub(conditions, SAML_NS, "AudienceRestriction")
    _sub(restriction, SAML_NS, "Audience", params.sp_entity_id)

    authn = _sub(
        assertion,
        SAML_NS,
        "AuthnStatement",
        AuthnInstant=_instant(now),
        SessionIndex=_new_id(),
    )
    context = _sub(authn, SAML_NS, "AuthnContext")
    _sub(context, SAML_NS, "AuthnContextClassRef", AUTHN_CONTEXT_PASSWORD_PROTECTED)

    if params.attributes:
        statement = _sub(assertion, SAML_NS, "AttributeStatement")
        for name, value in params.attributes.items():
            attribute = _sub(
                statement,
                SAML_NS,
                "Attribute",
                Name=name,
                NameFormat=ATTRNAME_FORMAT_BASIC,
            )
            attr_value = _sub(attribute, SAML_NS, "AttributeValue", value)
            attr_value.set(f"{{{XSI_NS}}}type", "xs:string")

    return _sign(assertion, cert) if params.sign_assertion else assertion


def build_response(params: ResponseParams, cert: SigningCert, now: datetime) -> bytes:
    """
    Build a SAML Response for ``params``, signed with ``cert``.

    The certificate's validity period is deliberately ignored: signing with an
    expired or not-yet-valid certificate is how SP date handling gets tested.
    """
    response = etree.Element(
        f"{{{SAMLP_NS}}}Response",
        {
            "ID": _new_id(),
            "Version": "2.0",
            "IssueInstant": _instant(now),
            "Destination": params.acs_url,
        },
        nsmap={"samlp": SAMLP_NS, "saml": SAML_NS},
    )
    if params.in_response_to:
        response.set("InResponseTo", params.in_response_to)
    _sub(response, SAML_NS, "Issuer", params.idp_entity_id)
    if params.sign_response:
        _signature_placeholder(response)
    status = _sub(response, SAMLP_NS, "Status")
    _sub(status, SAMLP_NS, "StatusCode", Value=STATUS_SUCCESS)
    response.append(_build_assertion(params, cert, now))

    if params.sign_response:
        response = _sign(response, cert)
    return etree.tostring(response, xml_declaration=True, encoding="UTF-8")
