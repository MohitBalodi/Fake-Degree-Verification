"""Ed25519 key handling. Signing/verification of certificate records lands with
Tier 1 item 3; for now this only generates and stores institution keypairs."""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.config import settings


def private_key_path(institution_code: str) -> Path:
    return Path(settings.keys_dir) / f"{institution_code}.pem"


def public_key_pem(private_key: Ed25519PrivateKey) -> str:
    return (
        private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode("ascii")
    )


def load_or_create_private_key(institution_code: str) -> Ed25519PrivateKey:
    """Load `<KEYS_DIR>/<code>.pem`, generating it first if it doesn't exist."""
    path = private_key_path(institution_code)
    if path.exists():
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError(f"{path} is not an Ed25519 private key")
        return key

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
