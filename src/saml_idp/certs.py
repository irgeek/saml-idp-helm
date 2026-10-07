"""Generation and loading of the IdP's signing certificates."""

import base64
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


CERT_SUFFIX = ".crt"
KEY_SUFFIX = ".key"
KEY_SIZE = 2048
# Backdate "valid" certificates slightly so small clock skew between the IdP
# and SP doesn't make them look not-yet-valid.
CLOCK_SKEW_ALLOWANCE = timedelta(minutes=5)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CertSpec:
    """A certificate to generate, with validity relative to generation time."""

    name: str
    not_before: timedelta
    not_after: timedelta


CERT_SPECS = (
    CertSpec("valid-1", -CLOCK_SKEW_ALLOWANCE, timedelta(days=365)),
    CertSpec("valid-2", -CLOCK_SKEW_ALLOWANCE, timedelta(days=365)),
    CertSpec("expired", timedelta(days=-366), timedelta(days=-1)),
    CertSpec("not-yet-valid", timedelta(days=365), timedelta(days=730)),
)


class CertStatus(StrEnum):
    VALID = "valid"
    EXPIRED = "expired"
    NOT_YET_VALID = "not yet valid"


@dataclass(frozen=True)
class SigningCert:
    name: str
    cert: x509.Certificate
    key: rsa.RSAPrivateKey

    @property
    def not_before(self) -> datetime:
        return self.cert.not_valid_before_utc

    @property
    def not_after(self) -> datetime:
        return self.cert.not_valid_after_utc

    @property
    def pem(self) -> str:
        return self.cert.public_bytes(serialization.Encoding.PEM).decode("ascii")

    @property
    def der_base64(self) -> str:
        """The certificate body as it appears in ``<ds:X509Certificate>``."""
        der = self.cert.public_bytes(serialization.Encoding.DER)
        return base64.b64encode(der).decode("ascii")

    @property
    def sha256_fingerprint(self) -> str:
        return self.cert.fingerprint(hashes.SHA256()).hex(":").upper()

    def status(self, now: datetime) -> CertStatus:
        if now < self.not_before:
            return CertStatus.NOT_YET_VALID
        if now > self.not_after:
            return CertStatus.EXPIRED
        return CertStatus.VALID


def generate_cert(
    name: str, not_before: datetime, not_after: datetime
) -> tuple[bytes, bytes]:
    """Create a self-signed RSA certificate, returning ``(cert_pem, key_pem)``."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=KEY_SIZE)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, f"saml-idp {name}"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test SAML IdP"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def write_certs(directory: Path, now: datetime) -> list[Path]:
    """Generate every certificate in :data:`CERT_SPECS` into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for spec in CERT_SPECS:
        cert_pem, key_pem = generate_cert(
            spec.name, now + spec.not_before, now + spec.not_after
        )
        cert_path = directory / f"{spec.name}{CERT_SUFFIX}"
        key_path = directory / f"{spec.name}{KEY_SUFFIX}"
        cert_path.write_bytes(cert_pem)
        key_path.touch(mode=0o600)
        key_path.write_bytes(key_pem)
        written.append(cert_path)
    return written


def _sort_key(cert: SigningCert) -> tuple[int, str]:
    names = [spec.name for spec in CERT_SPECS]
    rank = names.index(cert.name) if cert.name in names else len(names)
    return rank, cert.name


def load_certs(directory: Path) -> list[SigningCert]:
    """
    Load every ``<name>.crt``/``<name>.key`` pair in ``directory``.

    Generated certificates come first in :data:`CERT_SPECS` order, followed by
    any extra pairs (e.g. mounted from a Secret) sorted by name.
    """
    certs = []
    for cert_path in directory.glob(f"*{CERT_SUFFIX}"):
        key_path = cert_path.with_suffix(KEY_SUFFIX)
        if not key_path.exists():
            logger.warning("Skipping %s: no matching %s", cert_path, key_path.name)
            continue
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            logger.warning("Skipping %s: only RSA keys are supported", key_path)
            continue
        certs.append(SigningCert(name=cert_path.stem, cert=cert, key=key))
    return sorted(certs, key=_sort_key)
