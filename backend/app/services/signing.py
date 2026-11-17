"""Ed25519 signing of canonical certificate records, plus institution key files.

Canonical record (see the project spec, "Signing & QR"): JSON of the nine fields below,
values normalized, keys sorted, separators (",", ":"), UTF-8. The signature is
Ed25519 over those bytes, base64url without padding.

`canonical_bytes`, `sign_record` and `verify_record` are pure (no I/O). Only the
key-file helpers touch disk.
"""

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.core.config import settings
from app.services.normalize import (
    format_date,
    format_decimal,
    normalize_id,
    normalize_text,
    normalize_year,
)


@dataclass(frozen=True)
class CertificateRecord:
    cert_number: str
    institution_code: str
    student_name: str
    roll_number: str
    programme: str
    year_of_passing: int
    cgpa: Decimal | float | str | None
    marks: Decimal | float | str | None
    issue_date: date


def canonical_dict(record: CertificateRecord) -> dict[str, str | int | None]:
    return {
        "cert_number": normalize_id(record.cert_number),
        "institution_code": normalize_id(record.institution_code),
        "student_name": normalize_text(record.student_name),
        "roll_number": normalize_id(record.roll_number),
        "programme": normalize_text(record.programme),
        "year_of_passing": normalize_year(record.year_of_passing),
        # Strings ("8.50"), not JSON floats, so the bytes never depend on float repr.
        "cgpa": format_decimal(record.cgpa),
        "marks": format_decimal(record.marks),
        "issue_date": format_date(record.issue_date),
    }


def canonical_bytes(record: CertificateRecord) -> bytes:
    return json.dumps(
        canonical_dict(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign_record(private_key: Ed25519PrivateKey, record: CertificateRecord) -> str:
    return _b64url(private_key.sign(canonical_bytes(record)))


def verify_record(public_key_pem: str, record: CertificateRecord, signature: str) -> bool:
    """True only if `signature` is a valid signature of `record` by this key."""
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("ascii"))
        if not isinstance(public_key, Ed25519PublicKey):
            return False
        public_key.verify(_b64url_decode(signature), canonical_bytes(record))
        return True
    except (InvalidSignature, ValueError, binascii.Error, UnicodeEncodeError):
        return False


# --- key files ---------------------------------------------------------------


class SigningKeyMissing(Exception):
    pass


def private_key_path(institution_code: str) -> Path:
    return Path(settings.keys_dir) / f"{institution_code}.pem"


def public_key_pem(private_key: Ed25519PrivateKey) -> str:
    return (
        private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode("ascii")
    )


def load_private_key(institution_code: str) -> Ed25519PrivateKey:
    """Load `<KEYS_DIR>/<code>.pem`. Raises SigningKeyMissing if absent."""
    path = private_key_path(institution_code)
    if not path.exists():
        raise SigningKeyMissing(f"No signing key for institution {institution_code}")
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(f"{path} is not an Ed25519 private key")
    return key


def load_or_create_private_key(institution_code: str) -> Ed25519PrivateKey:
    """Load `<KEYS_DIR>/<code>.pem`, generating it first if it doesn't exist."""
    path = private_key_path(institution_code)
    if path.exists():
        return load_private_key(institution_code)

    key = Ed25519PrivateKey.generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    path.chmod(0o600)
    return key
