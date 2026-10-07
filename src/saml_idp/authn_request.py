"""Decoding and parsing of SP-initiated SAML AuthnRequests."""

import base64
import binascii
import zlib
from dataclasses import dataclass

from lxml import etree


SAMLP_NS = "urn:oasis:names:tc:SAML:2.0:protocol"
SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"

# AuthnRequests are untrusted input: never resolve entities or fetch anything.
_PARSER = etree.XMLParser(
    resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False
)


class AuthnRequestError(ValueError):
    """Raised when a SAMLRequest can't be decoded or isn't an AuthnRequest."""


@dataclass(frozen=True)
class AuthnRequest:
    id: str
    issuer: str | None
    acs_url: str | None
    protocol_binding: str | None


def decode_saml_request(encoded: str) -> bytes:
    """
    Decode a ``SAMLRequest`` parameter from either binding.

    The HTTP-Redirect binding DEFLATEs the XML before base64-encoding it; the
    HTTP-POST binding doesn't.  Rather than trusting the transport, detect
    which one was used from the decoded bytes.
    """
    try:
        raw = base64.b64decode(encoded, validate=False)
    except (binascii.Error, ValueError):
        raise AuthnRequestError("SAMLRequest is not valid base64")
    if raw.lstrip().startswith(b"<"):
        return raw
    try:
        return zlib.decompress(raw, -zlib.MAX_WBITS)
    except zlib.error:
        raise AuthnRequestError("SAMLRequest is neither XML nor DEFLATE-compressed XML")


def parse_authn_request(xml: bytes) -> AuthnRequest:
    try:
        root = etree.fromstring(xml, parser=_PARSER)
    except etree.XMLSyntaxError as e:
        raise AuthnRequestError(f"SAMLRequest is not well-formed XML: {e}")
    if root.tag != f"{{{SAMLP_NS}}}AuthnRequest":
        raise AuthnRequestError(f"expected a samlp:AuthnRequest, got {root.tag}")
    request_id = root.get("ID")
    if not request_id:
        raise AuthnRequestError("AuthnRequest has no ID attribute")
    issuer = root.findtext(f"{{{SAML_NS}}}Issuer")
    return AuthnRequest(
        id=request_id,
        issuer=issuer.strip() if issuer else None,
        acs_url=root.get("AssertionConsumerServiceURL"),
        protocol_binding=root.get("ProtocolBinding"),
    )
