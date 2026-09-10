"""
Auth domain
===========
Credentials and session identity only. Persona/preferences live in the
``users`` module, keyed by the same account id (24.2: "auth, users and
profiles" are separate components).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if not _EMAIL_RE.match(normalized):
            raise InvalidEmailError(self.value)
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(slots=True)
class AuthAccount:
    """The credential/session aggregate — never exposed with its password hash."""

    email: Email
    hashed_password: str
    consented_at: datetime
    is_admin: bool = False
    is_active: bool = True
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_locked(self) -> bool:
        return self.locked_until is not None and self.locked_until > datetime.now(UTC)

    def register_failed_login(self, *, max_attempts: int, lockout_minutes: int) -> None:
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.now(UTC) + timedelta(minutes=lockout_minutes)
        self.updated_at = datetime.now(UTC)

    def register_successful_login(self) -> None:
        self.failed_login_attempts = 0
        self.locked_until = None
        self.updated_at = datetime.now(UTC)


@dataclass(slots=True)
class RefreshToken:
    """Stored only as a hash; rotated on every use with reuse detection."""

    account_id: UUID
    token_hash: str
    expires_at: datetime
    id: UUID = field(default_factory=uuid4)
    revoked_at: datetime | None = None
    replaced_by_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_valid(self) -> bool:
        return self.revoked_at is None and self.expires_at > datetime.now(UTC)


class AuthAccountRepository(Protocol):
    async def add(self, account: AuthAccount) -> AuthAccount: ...
    async def get_by_id(self, account_id: UUID) -> AuthAccount | None: ...
    async def get_by_email(self, email: Email) -> AuthAccount | None: ...
    async def update(self, account: AuthAccount) -> AuthAccount: ...
    async def delete(self, account_id: UUID) -> None: ...


class RefreshTokenRepository(Protocol):
    async def add(self, token: RefreshToken) -> RefreshToken: ...
    async def get_by_hash(self, token_hash: str) -> RefreshToken | None: ...
    async def revoke(self, token_id: UUID, *, replaced_by_id: UUID | None = None) -> None: ...
    async def revoke_all_for_account(self, account_id: UUID) -> None: ...


class InvalidEmailError(ValueError):
    def __init__(self, value: str) -> None:
        super().__init__(f"'{value}' is not a valid email address")


class EmailAlreadyRegisteredError(Exception):
    def __init__(self) -> None:
        super().__init__("An account with this email already exists")


class InvalidCredentialsError(Exception):
    def __init__(self) -> None:
        super().__init__("Incorrect email or password")


class AccountLockedError(Exception):
    def __init__(self, locked_until: datetime) -> None:
        self.locked_until = locked_until
        super().__init__("Account temporarily locked after repeated failed logins")


class InvalidRefreshTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Refresh token is invalid, expired, or already used")
