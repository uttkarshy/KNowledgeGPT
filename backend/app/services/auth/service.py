"""
Auth business logic. This is the only layer that touches User/RefreshToken
rows directly — API routes call these functions and never write raw queries.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    generate_url_safe_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.enums import AuthProvider, UserRole
from app.models.user import RefreshToken, User
from app.services.auth.google_oauth import GoogleUserInfo
from app.services.email_service import send_password_reset_email, send_verification_email


class AuthError(Exception):
    """Base class for all auth-flow errors. Routes map these to HTTP 400/401/403."""


class InvalidCredentialsError(AuthError):
    pass


class EmailAlreadyRegisteredError(AuthError):
    pass


class AccountSuspendedError(AuthError):
    pass


class InvalidOrExpiredTokenError(AuthError):
    pass


class TokenPair:
    def __init__(self, access_token: str, refresh_token: str, expires_in: int):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in


# ----------------------------------------------------------------------
# Registration / login
# ----------------------------------------------------------------------
async def register_user(
    db: AsyncSession, *, settings: Settings, email: str, password: str, full_name: Optional[str]
) -> User:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing:
        raise EmailAlreadyRegisteredError(f"An account with email {email} already exists")

    verification_token = generate_url_safe_token()
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=UserRole.USER,
        auth_provider=AuthProvider.PASSWORD,
        is_verified=False,
        email_verification_token=hash_token(verification_token),
    )
    db.add(user)
    await db.flush()  # populate user.id without committing yet

    await send_verification_email(settings, to=user.email, token=verification_token)
    return user


async def authenticate_user(db: AsyncSession, *, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Incorrect email or password")
    if user.is_suspended or not user.is_active:
        raise AccountSuspendedError("This account has been suspended")

    user.last_login_at = datetime.now(timezone.utc)
    return user


# ----------------------------------------------------------------------
# Google OAuth
# ----------------------------------------------------------------------
async def get_or_create_google_user(
    db: AsyncSession, *, google_info: GoogleUserInfo
) -> User:
    user = await db.scalar(select(User).where(User.google_id == google_info.sub))
    if user:
        if user.is_suspended or not user.is_active:
            raise AccountSuspendedError("This account has been suspended")
        user.last_login_at = datetime.now(timezone.utc)
        return user

    if not google_info.email_verified:
        raise InvalidCredentialsError("Google email must be verified")

    # Link by email if a password account already exists with this address.
    user = await db.scalar(select(User).where(User.email == google_info.email))
    if user:
        if user.is_suspended or not user.is_active:
            raise AccountSuspendedError("This account has been suspended")
        user.google_id = google_info.sub
        if google_info.email_verified:
            user.is_verified = True
        user.last_login_at = datetime.now(timezone.utc)
        return user

    user = User(
        email=google_info.email,
        hashed_password=None,
        full_name=google_info.name,
        role=UserRole.USER,
        auth_provider=AuthProvider.GOOGLE,
        google_id=google_info.sub,
        is_verified=google_info.email_verified,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    return user


# ----------------------------------------------------------------------
# Token issuance / rotation / revocation
# ----------------------------------------------------------------------
async def issue_token_pair(
    db: AsyncSession, *, user: User, settings: Settings, user_agent: Optional[str], ip_address: Optional[str]
) -> TokenPair:
    access_token = create_access_token(user_id=user.id, role=user.role.value, settings=settings)

    plaintext_refresh, refresh_hash = generate_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    )

    return TokenPair(
        access_token=access_token,
        refresh_token=plaintext_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def rotate_refresh_token(
    db: AsyncSession,
    *,
    settings: Settings,
    plaintext_refresh_token: str,
    user_agent: Optional[str],
    ip_address: Optional[str],
) -> TokenPair:
    """Verifies the presented refresh token, revokes it, and issues a new
    pair (refresh token rotation). If a revoked token is presented again —
    a strong signal of theft/replay — all of that user's tokens are revoked
    as a precaution."""
    token_hash = hash_token(plaintext_refresh_token)
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update())

    if not stored:
        raise InvalidOrExpiredTokenError("Refresh token not recognized")

    if stored.revoked:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == stored.user_id, RefreshToken.revoked == False)  # noqa: E712
            .values(revoked=True)
        )
        await db.commit()  # preserve revocation even though the route returns 401
        raise InvalidOrExpiredTokenError(
            "This refresh token was already used. All sessions have been revoked as a precaution."
        )

    if stored.expires_at < datetime.now(timezone.utc):
        raise InvalidOrExpiredTokenError("Refresh token has expired")

    user = await db.get(User, stored.user_id)
    if not user or user.is_suspended or not user.is_active:
        raise AccountSuspendedError("This account has been suspended")

    stored.revoked = True
    new_pair = await issue_token_pair(
        db, user=user, settings=settings, user_agent=user_agent, ip_address=ip_address
    )
    # Record the successor hash for audit/debugging of rotation chains.
    stored.replaced_by_token_hash = hash_token(new_pair.refresh_token)
    return new_pair


async def revoke_refresh_token(db: AsyncSession, *, plaintext_refresh_token: str) -> None:
    token_hash = hash_token(plaintext_refresh_token)
    await db.execute(
        update(RefreshToken).where(RefreshToken.token_hash == token_hash).values(revoked=True)
    )


async def revoke_all_user_tokens(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True)
    )


# ----------------------------------------------------------------------
# Email verification
# ----------------------------------------------------------------------
async def verify_email(db: AsyncSession, *, token: str) -> User:
    user = await db.scalar(select(User).where(User.email_verification_token == hash_token(token)))
    if not user or user.created_at + timedelta(hours=get_settings().EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS) < datetime.now(timezone.utc):
        raise InvalidOrExpiredTokenError("Invalid or expired verification token")
    user.is_verified = True
    user.email_verification_token = None
    return user


# ----------------------------------------------------------------------
# Password reset
# ----------------------------------------------------------------------
async def request_password_reset(db: AsyncSession, *, settings: Settings, email: str) -> None:
    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        # Deliberately do not reveal whether the email exists.
        return
    reset_token = generate_url_safe_token()
    user.password_reset_token = hash_token(reset_token)
    user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    )
    await send_password_reset_email(settings, to=user.email, token=reset_token)


async def confirm_password_reset(db: AsyncSession, *, token: str, new_password: str) -> User:
    user = await db.scalar(select(User).where(User.password_reset_token == hash_token(token)))
    if (
        not user
        or not user.password_reset_expires_at
        or user.password_reset_expires_at < datetime.now(timezone.utc)
    ):
        raise InvalidOrExpiredTokenError("Invalid or expired password reset token")

    user.hashed_password = hash_password(new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    await revoke_all_user_tokens(db, user_id=user.id)  # force re-login everywhere
    return user
