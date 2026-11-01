"""Encryption for the Cloudflare R2 credentials an admin pastes into the panel.

Why this exists: ``R2Account`` holds an access key id and a secret access key
for somebody's Cloudflare account. A database dump — a support copy, a backup
bucket, a read-only replica handed to a contractor — must not contain working
credentials. Both values are therefore encrypted before they are written, and
the plaintext exists only in memory for the duration of one request.

Key material
------------
``settings.R2_CREDENTIAL_KEYS`` is a list of urlsafe-base64 32-byte keys, first
one active. When it is empty a key is derived from ``SECRET_KEY`` so that a
development machine works with no setup. That fallback is documented as unfit
for production: rotating ``SECRET_KEY`` there makes every stored token
unreadable, and the rotation command exists precisely to avoid that with an
explicit key.

Every value is prefixed with ``v1:`` so a future scheme can be introduced
without guessing at the contents of old rows.

Rotation
--------
``MultiFernet`` decrypts with any key in the list and encrypts with the first.
``manage.py r2_rotate_key`` re-encrypts every stored secret once a new key has
been added to the front of the variable, so the old one can then be dropped.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

__all__ = ["PREFIX", "encrypt", "decrypt", "fingerprint", "derive_key", "generate_key"]

PREFIX = "v1:"

# Domain separation: a key derived for this purpose cannot be reused as a
# SECRET_KEY by accident, and vice versa.
_KDF_SALT = b"studyspace.r2.credentials"
_KDF_INFO = b"fernet-key-v1"


class CredentialError(RuntimeError):
    """A stored credential cannot be read with the configured keys."""


def derive_key(secret_key: str) -> str:
    """HKDF-SHA256(secret_key) → urlsafe-base64 Fernet key.

    HMAC is the extract step and one expansion block is enough for 32 bytes,
    which is exactly what Fernet wants.
    """
    prk = hmac.new(_KDF_SALT, secret_key.encode("utf-8"), hashlib.sha256).digest()
    okm = hmac.new(prk, _KDF_INFO + b"\x01", hashlib.sha256).digest()
    return base64.urlsafe_b64encode(okm).decode("ascii")


def generate_key() -> str:
    """A fresh key for ``R2_CREDENTIAL_KEYS``."""
    return Fernet.generate_key().decode("ascii")


def _configured_keys() -> list[str]:
    keys = [key for key in (getattr(settings, "R2_CREDENTIAL_KEYS", None) or []) if key]
    if keys:
        return keys
    if not settings.SECRET_KEY:
        raise CredentialError("No encryption key is configured.")
    return [derive_key(settings.SECRET_KEY)]


def _fernet() -> MultiFernet:
    return MultiFernet([Fernet(key) for key in _configured_keys()])


def encrypt(plaintext: str) -> str:
    """Encrypt a credential for storage. Returns ``v1:<token>``."""
    if not plaintext:
        raise ValueError("Refusing to encrypt an empty credential.")
    token = _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{PREFIX}{token}"


def decrypt(stored: str) -> str:
    """Decrypt a stored credential.

    Raises :class:`CredentialError` when the value was written with a key that
    is no longer configured — a state the admin must see as "re-enter the
    token", never as a 500 with a stack trace.
    """
    if not stored:
        raise CredentialError("No credential is stored.")
    token = stored[len(PREFIX):] if stored.startswith(PREFIX) else stored
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        raise CredentialError(
            "This credential cannot be decrypted with the configured keys. "
            "Re-enter the API token."
        ) from exc


def fingerprint(value: str) -> str:
    """A short, non-reversible handle for a credential: ``••••1a2b``.

    Enough to tell two tokens apart in a list, useless to anyone who reads it.
    """
    if not value:
        return ""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"••••{digest[:4]}"
