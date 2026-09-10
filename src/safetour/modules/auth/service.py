"""Auth application service: registration, login, token refresh and reuse detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from safetour.modules.auth.domain import (
    AccountLockedError,
    AuthAccount,
    AuthAccountRepository,
    Email,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshToken,
    RefreshTokenRepository,
)
from safetour.shared.config import settings
from safetour.shared.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


@dataclass(slots=True)
class RegisterInput:
    email: str
    password: str
    consent: bool


@dataclass(slots=True)
class LoginInput:
    email: str
    password: str


@dataclass(slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    account_id: UUID
    token_type: str = "bearer"


class AuthService:
    def __init__(self, accounts: AuthAccountRepository, refresh_tokens: RefreshTokenRepository) -> None:
        self._accounts = accounts
        self._refresh_tokens = refresh_tokens

    async def register(self, data: RegisterInput) -> AuthAccount:
        if not data.consent:
            raise ValueError("Explicit consent is required to register (NFR-PRIV-1)")
        email = Email(data.email)
        if await self._accounts.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError()
        account = AuthAccount(
            email=email,
            hashed_password=hash_password(data.password),
            consented_at=datetime.now(UTC),
        )
        return await self._accounts.add(account)

    async def login(self, data: LoginInput) -> tuple[AuthAccount, TokenPair]:
        email = Email(data.email)
        account = await self._accounts.get_by_email(email)
        if account is None or not account.is_active:
            raise InvalidCredentialsError()
        if account.is_locked():
            assert account.locked_until is not None
            raise AccountLockedError(account.locked_until)
        if not verify_password(data.password, account.hashed_password):
            account.register_failed_login(
                max_attempts=settings.MAX_LOGIN_ATTEMPTS,
                lockout_minutes=settings.LOCKOUT_MINUTES,
            )
            await self._accounts.update(account)
            raise InvalidCredentialsError()

        account.register_successful_login()
        await self._accounts.update(account)
        tokens = await self._issue_tokens(account.id)
        return account, tokens

    async def refresh(self, plaintext_refresh_token: str) -> TokenPair:
        token_hash = hash_refresh_token(plaintext_refresh_token)
        stored = await self._refresh_tokens.get_by_hash(token_hash)
        if stored is None:
            raise InvalidRefreshTokenError()
        if not stored.is_valid():
            # Reuse of a rotated/expired token is a strong signal of theft:
            # burn every refresh token for the account (NFR-SEC-2).
            await self._refresh_tokens.revoke_all_for_account(stored.account_id)
            raise InvalidRefreshTokenError()
        return await self._issue_tokens(stored.account_id, supersedes=stored)

    async def logout(self, account_id: UUID) -> None:
        await self._refresh_tokens.revoke_all_for_account(account_id)

    async def delete_account(self, account_id: UUID) -> None:
        """FR-AUTH-5: honour a deletion request — revoke sessions, then erase credentials."""
        await self._refresh_tokens.revoke_all_for_account(account_id)
        await self._accounts.delete(account_id)

    async def _issue_tokens(self, account_id: UUID, supersedes: RefreshToken | None = None) -> TokenPair:
        plaintext, token_hash, expires_at = generate_refresh_token()
        new_token = RefreshToken(account_id=account_id, token_hash=token_hash, expires_at=expires_at)
        new_token = await self._refresh_tokens.add(new_token)
        if supersedes is not None:
            await self._refresh_tokens.revoke(supersedes.id, replaced_by_id=new_token.id)
        access_token = create_access_token(subject=account_id)
        return TokenPair(access_token=access_token, refresh_token=plaintext, account_id=account_id)
