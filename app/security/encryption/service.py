"""
AES-256-GCM field-level encryption for sensitive database columns.

Provides:
  EncryptionService         — encrypt / decrypt individual values
  encrypt_field()           — one-shot convenience wrapper
  decrypt_field()           — one-shot convenience wrapper
  EncryptedStr              — SQLAlchemy TypeDecorator for encrypted TEXT columns

Design decisions:
  - AES-256-GCM: authenticated encryption (confidentiality + integrity + authenticity)
  - Random 96-bit IV per encryption call: prevents IV reuse attacks
  - Key derivation via HKDF-SHA256 from the app secret_key + salt
  - Version prefix on ciphertext (v1:...) for future key rotation support
  - No key material is ever stored in the database — only ciphertexts
  - decrypt_field() returns None on any error (never raises; prevents oracle attacks)

Usage:
    svc = EncryptionService.from_settings()

    ciphertext = svc.encrypt("sensitive value")
    plaintext  = svc.decrypt(ciphertext)

    # In SQLAlchemy models:
    from app.security.encryption.service import EncryptedStr

    class PACase(Base):
        member_id: Mapped[str | None] = mapped_column(EncryptedStr)
"""

from __future__ import annotations

import base64
import os
from functools import lru_cache
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_VERSION_PREFIX = b"v1:"
_IV_LENGTH      = 12    # 96 bits — GCM standard
_TAG_LENGTH     = 16    # 128-bit authentication tag


class EncryptionService:
    """
    AES-256-GCM field-level encryption service.

    One instance per application (created via from_settings()).
    """

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("Encryption key must be exactly 32 bytes (AES-256)")
        self._key = key

    # ------------------------------------------------------------------
    # Encrypt / decrypt
    # ------------------------------------------------------------------

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string value and return a base64-encoded ciphertext.

        Format: base64( b"v1:" + iv(12) + tag(16) + ciphertext )
        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            iv     = os.urandom(_IV_LENGTH)
            aesgcm = AESGCM(self._key)
            data   = plaintext.encode("utf-8")
            # AESGCM.encrypt returns ciphertext + tag concatenated
            ct_tag = aesgcm.encrypt(iv, data, None)

            raw = _VERSION_PREFIX + iv + ct_tag
            return base64.urlsafe_b64encode(raw).decode("ascii")

        except Exception as exc:
            logger.error("encryption.encrypt_failed", error=str(exc))
            raise

    def decrypt(self, ciphertext: str) -> str | None:
        """
        Decrypt a previously encrypted value.

        Returns None on any error to prevent timing-based oracle attacks.
        """
        if not ciphertext:
            return None
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            raw = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
            if not raw.startswith(_VERSION_PREFIX):
                logger.warning("encryption.unknown_version")
                return None

            raw    = raw[len(_VERSION_PREFIX):]
            iv     = raw[:_IV_LENGTH]
            ct_tag = raw[_IV_LENGTH:]

            aesgcm    = AESGCM(self._key)
            plaintext = aesgcm.decrypt(iv, ct_tag, None)
            return plaintext.decode("utf-8")

        except Exception:
            return None

    def encrypt_dict(self, data: dict[str, Any], fields: list[str]) -> dict[str, Any]:
        """Encrypt specified fields in a dict, returning a copy."""
        result = dict(data)
        for field in fields:
            if field in result and result[field] is not None:
                result[field] = self.encrypt(str(result[field]))
        return result

    def decrypt_dict(self, data: dict[str, Any], fields: list[str]) -> dict[str, Any]:
        """Decrypt specified fields in a dict, returning a copy."""
        result = dict(data)
        for field in fields:
            if field in result and result[field] is not None:
                result[field] = self.decrypt(str(result[field]))
        return result

    # ------------------------------------------------------------------
    # Key derivation helper
    # ------------------------------------------------------------------

    @classmethod
    def derive_key(cls, master_secret: str, salt: str = "pa-review-platform") -> bytes:
        """Derive a 256-bit key from the master secret using HKDF-SHA256."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode("utf-8"),
            info=b"field-encryption-key",
        )
        return hkdf.derive(master_secret.encode("utf-8"))

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_settings(cls) -> "EncryptionService":
        """Create an EncryptionService from application settings."""
        from app.core.config.settings import get_settings
        settings   = get_settings()
        master_key = settings.secret_key.get_secret_value()
        derived    = cls.derive_key(master_key)
        return cls(key=derived)


@lru_cache(maxsize=1)
def get_encryption_service() -> EncryptionService:
    """Return the cached EncryptionService singleton."""
    return EncryptionService.from_settings()


def encrypt_field(value: str | None) -> str | None:
    """Convenience: encrypt a single field value, returning None if input is None."""
    if value is None:
        return None
    return get_encryption_service().encrypt(value)


def decrypt_field(value: str | None) -> str | None:
    """Convenience: decrypt a single field value, returning None if input is None."""
    if value is None:
        return None
    return get_encryption_service().decrypt(value)


# ---------------------------------------------------------------------------
# SQLAlchemy TypeDecorator
# ---------------------------------------------------------------------------

try:
    from sqlalchemy import String
    from sqlalchemy.types import TypeDecorator

    class EncryptedStr(TypeDecorator):
        """
        SQLAlchemy column type that transparently encrypts/decrypts TEXT values.

        Usage:
            class SensitiveModel(Base):
                ssn: Mapped[str | None] = mapped_column(EncryptedStr(length=512))
        """

        impl = String
        cache_ok = True

        def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
            """Encrypt on write (Python → DB)."""
            return encrypt_field(value)

        def process_result_value(self, value: str | None, dialect: Any) -> str | None:
            """Decrypt on read (DB → Python)."""
            return decrypt_field(value)

except ImportError:
    EncryptedStr = None  # type: ignore[assignment,misc]
