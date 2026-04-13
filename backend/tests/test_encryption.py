"""Tests for app.common.encryption."""

import pytest
from cryptography.fernet import Fernet

from app.common.encryption import (
    EncryptionError,
    decrypt_optional,
    decrypt_token,
    encrypt_optional,
    encrypt_token,
)


class TestEncryptToken:
    def test_round_trip(self) -> None:
        """Encrypt then decrypt returns the original."""
        plaintext = "ya29.a0AfH6SMBxBKbZ_token"
        ciphertext = encrypt_token(plaintext)
        assert ciphertext != plaintext  # actually encrypted
        assert decrypt_token(ciphertext) == plaintext

    def test_unique_ciphertexts(self) -> None:
        """Same plaintext encrypted twice produces different ciphertexts (Fernet uses random IV)."""
        plaintext = "secret-token"
        a = encrypt_token(plaintext)
        b = encrypt_token(plaintext)
        assert a != b
        assert decrypt_token(a) == plaintext
        assert decrypt_token(b) == plaintext

    def test_long_token(self) -> None:
        """Long tokens (e.g., JWTs) round-trip correctly."""
        plaintext = "x" * 4096
        assert decrypt_token(encrypt_token(plaintext)) == plaintext

    def test_unicode_token(self) -> None:
        plaintext = "tøken-with-üñíçödé-✓"
        assert decrypt_token(encrypt_token(plaintext)) == plaintext

    def test_empty_string_rejected_for_encrypt(self) -> None:
        with pytest.raises(EncryptionError, match="empty"):
            encrypt_token("")

    def test_empty_string_rejected_for_decrypt(self) -> None:
        with pytest.raises(EncryptionError, match="empty"):
            decrypt_token("")


class TestTamperDetection:
    def test_tampered_ciphertext_raises(self) -> None:
        """Modifying the ciphertext must raise EncryptionError."""
        ciphertext = encrypt_token("important-token")
        # Flip a character in the middle
        tampered = ciphertext[:50] + ("A" if ciphertext[50] != "A" else "B") + ciphertext[51:]
        with pytest.raises(EncryptionError, match="Invalid or tampered"):
            decrypt_token(tampered)

    def test_random_garbage_raises(self) -> None:
        with pytest.raises(EncryptionError):
            decrypt_token("not-a-real-fernet-token")

    def test_truncated_ciphertext_raises(self) -> None:
        ciphertext = encrypt_token("token")
        with pytest.raises(EncryptionError):
            decrypt_token(ciphertext[:20])

    def test_wrong_key_raises(self) -> None:
        """A token encrypted with key A should not decrypt with key B."""
        # Encrypt with our key
        ciphertext = encrypt_token("token")
        # Manually decrypt with a different key — should fail
        other_cipher = Fernet(Fernet.generate_key())
        from cryptography.fernet import InvalidToken
        with pytest.raises(InvalidToken):
            other_cipher.decrypt(ciphertext.encode())


class TestOptionalHelpers:
    def test_encrypt_optional_passes_none_through(self) -> None:
        assert encrypt_optional(None) is None

    def test_decrypt_optional_passes_none_through(self) -> None:
        assert decrypt_optional(None) is None

    def test_encrypt_optional_round_trip(self) -> None:
        plaintext = "token"
        ciphertext = encrypt_optional(plaintext)
        assert ciphertext is not None
        assert decrypt_optional(ciphertext) == plaintext
