"""Generation of the IdP's SAML metadata document."""

from lxml import etree

from saml_idp.certs import SigningCert
from saml_idp.saml_response import DS_NS, NAMEID_FORMAT_EMAIL, SAMLP_NS


MD_NS = "urn:oasis:names:tc:SAML:2.0:metadata"
BINDING_REDIRECT = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
BINDING_POST = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"


def build_metadata(entity_id: str, sso_url: str, cert: SigningCert) -> bytes:
    descriptor = etree.Element(
        f"{{{MD_NS}}}EntityDescriptor",
        {"entityID": entity_id},
        nsmap={"md": MD_NS, "ds": DS_NS},
    )
    idp = etree.SubElement(
        descriptor,
        f"{{{MD_NS}}}IDPSSODescriptor",
        {"WantAuthnRequestsSigned": "false", "protocolSupportEnumeration": SAMLP_NS},
    )
    key_descriptor = etree.SubElement(idp, f"{{{MD_NS}}}KeyDescriptor", use="signing")
    key_info = etree.SubElement(key_descriptor, f"{{{DS_NS}}}KeyInfo")
    x509_data = etree.SubElement(key_info, f"{{{DS_NS}}}X509Data")
    etree.SubElement(x509_data, f"{{{DS_NS}}}X509Certificate").text = cert.der_base64
    etree.SubElement(idp, f"{{{MD_NS}}}NameIDFormat").text = NAMEID_FORMAT_EMAIL
    for binding in (BINDING_REDIRECT, BINDING_POST):
        etree.SubElement(
            idp,
            f"{{{MD_NS}}}SingleSignOnService",
            Binding=binding,
            Location=sso_url,
        )
    return etree.tostring(
        descriptor, xml_declaration=True, encoding="UTF-8", pretty_print=True
    )
