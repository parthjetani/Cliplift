"""Application-layer encryption for sensitive data at rest.

Used to encrypt OAuth `access_token` and `refresh_token` values before they
hit the database. The DB never sees plaintext credentials.

Uses `cryptography.fernet` (AES-128-CBC + HMAC-SHA256). The key is a 32-byte
URL-safe base64 string from `settings.ENCRYPTION_KEY`. Generate a new key with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Tamper detection is built into Fernet — any modification to the ciphertext
raises `cryptography.fernet.InvalidToken`.
"""

import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)


class EncryptionError(ValueError):
    """Raised when encryption or decryption fails."""


@lru_cache(maxsize=1)
def _get_cipher() -> Fernet:
    """Lazy singleton for the Fernet cipher (key validation happens once)."""
    key = settings.ENCRYPTION_KEY
    if not key:
        raise EncryptionError(
            "ENCRYPTION_KEY is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as e:
        raise EncryptionError(
            f"ENCRYPTION_KEY is malformed (must be a 32-byte URL-safe base64 string): {e}"
        ) from e


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token. Returns a URL-safe base64 string ready for DB storage.

    Raises:
        EncryptionError: If encryption fails or the input is empty.
    """
    if not plaintext:
        raise EncryptionError("Cannot encrypt an empty token")
    cipher = _get_cipher()
    return cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a previously-encrypted token.

    Raises:
        EncryptionError: If the ciphertext is tampered, corrupted, or wasn't
            encrypted with the current key.
    """
    if not ciphertext:
        raise EncryptionError("Cannot decrypt an empty value")
    cipher = _get_cipher()
    try:
        return cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        logger.warning("Token decryption failed — possible tamper or key rotation")
        raise EncryptionError("Invalid or tampered ciphertext") from e


def encrypt_optional(plaintext: str | None) -> str | None:
    """Encrypt only if not None — for optional DB columns."""
    if plaintext is None:
        return None
    return encrypt_token(plaintext)


def decrypt_optional(ciphertext: str | None) -> str | None:
    """Decrypt only if not None — for optional DB columns."""
    if ciphertext is None:
        return None
    return decrypt_token(ciphertext)
