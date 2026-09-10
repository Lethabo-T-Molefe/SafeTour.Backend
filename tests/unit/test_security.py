"""Unit tests for password hashing, JWTs and refresh tokens (NFR-SEC-1/2)."""

import jwt
import pytest

from safetour.shared.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_password_hash_is_not_plaintext() -> None:
    assert hash_password("secret1234") != "secret1234"


def test_access_token_roundtrip() -> None:
    token = create_access_token(subject="user-123")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_access_token_rejects_tampering() -> None:
    token = create_access_token(subject="user-123")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered)


def test_refresh_token_is_stored_only_as_a_hash() -> None:
    plaintext, token_hash, expires_at = generate_refresh_token()
    assert plaintext != token_hash
    assert hash_refresh_token(plaintext) == token_hash
    assert expires_at.tzinfo is not None
