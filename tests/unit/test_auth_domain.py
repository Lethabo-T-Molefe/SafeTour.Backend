"""Unit tests for the auth domain: email validation and lockout (FR-AUTH-1/2)."""

from datetime import UTC, datetime

import pytest

from safetour.modules.auth.domain import AuthAccount, Email, InvalidEmailError


def test_email_normalizes_case_and_whitespace() -> None:
    assert str(Email("  Ada@Example.COM ")) == "ada@example.com"


def test_email_rejects_invalid() -> None:
    with pytest.raises(InvalidEmailError):
        Email("not-an-email")


def _account() -> AuthAccount:
    return AuthAccount(email=Email("user@example.com"), hashed_password="x", consented_at=datetime.now(UTC))


def test_account_locks_after_max_attempts() -> None:
    account = _account()
    for _ in range(4):
        account.register_failed_login(max_attempts=5, lockout_minutes=15)
        assert not account.is_locked()
    account.register_failed_login(max_attempts=5, lockout_minutes=15)
    assert account.is_locked()


def test_successful_login_resets_lockout_state() -> None:
    account = _account()
    for _ in range(5):
        account.register_failed_login(max_attempts=5, lockout_minutes=15)
    assert account.is_locked()

    account.register_successful_login()
    assert not account.is_locked()
    assert account.failed_login_attempts == 0
