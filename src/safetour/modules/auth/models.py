"""SQLAlchemy models and repository implementations for the auth module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, select, update
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from safetour.modules.auth.domain import AuthAccount, Email, RefreshToken
from safetour.shared.database import Base


class AuthAccountModel(Base):
    __tablename__ = "auth_accounts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("auth_accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def _to_entity(row: AuthAccountModel) -> AuthAccount:
    return AuthAccount(
        id=row.id,
        email=Email(row.email),
        hashed_password=row.hashed_password,
        is_admin=row.is_admin,
        is_active=row.is_active,
        failed_login_attempts=row.failed_login_attempts,
        locked_until=row.locked_until,
        consented_at=row.consented_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyAuthAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, account: AuthAccount) -> AuthAccount:
        row = AuthAccountModel(
            id=account.id,
            email=str(account.email),
            hashed_password=account.hashed_password,
            is_admin=account.is_admin,
            is_active=account.is_active,
            consented_at=account.consented_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_entity(row)

    async def get_by_id(self, account_id: UUID) -> AuthAccount | None:
        row = await self._session.get(AuthAccountModel, account_id)
        return _to_entity(row) if row else None

    async def get_by_email(self, email: Email) -> AuthAccount | None:
        result = await self._session.execute(
            select(AuthAccountModel).where(AuthAccountModel.email == str(email))
        )
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def update(self, account: AuthAccount) -> AuthAccount:
        await self._session.execute(
            update(AuthAccountModel)
            .where(AuthAccountModel.id == account.id)
            .values(
                is_admin=account.is_admin,
                is_active=account.is_active,
                failed_login_attempts=account.failed_login_attempts,
                locked_until=account.locked_until,
            )
        )
        await self._session.flush()
        return account

    async def delete(self, account_id: UUID) -> None:
        row = await self._session.get(AuthAccountModel, account_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: RefreshToken) -> RefreshToken:
        row = RefreshTokenModel(
            id=token.id,
            account_id=token.account_id,
            token_hash=token.token_hash,
            expires_at=token.expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return RefreshToken(
            id=row.id,
            account_id=row.account_id,
            token_hash=row.token_hash,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            replaced_by_id=row.replaced_by_id,
            created_at=row.created_at,
        )

    async def revoke(self, token_id: UUID, *, replaced_by_id: UUID | None = None) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.id == token_id)
            .values(revoked_at=func.now(), replaced_by_id=replaced_by_id)
        )
        await self._session.flush()

    async def revoke_all_for_account(self, account_id: UUID) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.account_id == account_id, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
        await self._session.flush()
