"""
Security helpers
================
Argon2id password hashing (NFR-SEC-2), JWT access tokens, and opaque refresh
tokens that are stored only as a hash with rotation + reuse detection.

Domain entities store only ``hashed_password`` / ``token_hash`` — plaintext
secrets never reach persistence.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from safetour.shared.config import settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


def needs_rehash(hashed_password: str) -> bool:
    """True once Argon2 parameters have moved on from those used at hash time."""
    return _hasher.check_needs_rehash(hashed_password)


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """Issue a signed, short-lived JWT carrying ``subject`` as the ``sub`` claim."""
    expire = datetime.now(UTC) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": str(subject), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate and decode a JWT. Raises ``jwt.PyJWTError`` subclasses on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def generate_refresh_token() -> tuple[str, str, datetime]:
    """
    Issue an opaque refresh token.

    Returns ``(plaintext_token, token_hash, expires_at)``. Only ``token_hash``
    is persisted; ``plaintext_token`` is returned to the client once and never
    stored, so a stolen database dump cannot be replayed as a refresh token.
    """
    plaintext = secrets.token_urlsafe(48)
    token_hash = hash_refresh_token(plaintext)
    expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return plaintext, token_hash, expires_at


def hash_refresh_token(plaintext: str) -> str:
    """SHA-256 is sufficient here: refresh tokens are high-entropy random strings,
    not user-chosen secrets, so no deliberately-slow KDF is needed."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
