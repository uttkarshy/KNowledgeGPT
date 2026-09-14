"""
Password hashing + JWT primitives.

Design notes:
  - Access tokens are short-lived signed JWTs (claims: sub, role, type, jti, exp).
    They are never stored server-side — authentication also checks the user token version in the database.
  - Refresh tokens are OPAQUE random strings, not JWTs. Only their SHA-256
    hash is persisted (RefreshToken.token_hash), so a stolen DB dump can't be
    used to mint sessions, and revocation/rotation is a simple DB update
    rather than needing a token blocklist.
  - Secret rotation: if JWT_SECRET_KEY_PREVIOUS is set, tokens signed with it
    are still accepted (until they expire), while all new tokens are signed
    with JWT_SECRET_KEY. This allows rotating the secret with zero downtime.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ValidationError

from app.core.config import Settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ----------------------------------------------------------------------
# Passwords
# ----------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    if len(plain_password.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes")
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if len(plain_password.encode("utf-8")) > 72:
        return False
    return _pwd_context.verify(plain_password, hashed_password)


# ----------------------------------------------------------------------
# JWT access tokens
# ----------------------------------------------------------------------
class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"  # only used as a JWT `type` claim if we ever JWT-ify refresh; not used today


class TokenPayload(BaseModel):
    sub: str            # user id (UUID str)
    role: str
    type: str
    jti: str
    exp: int
    iat: int
    token_version: int = 0  # legacy JWTs belong to the initial session epoch


class InvalidTokenError(Exception):
    pass


def create_access_token(*, user_id: uuid.UUID, role: str, settings: Settings, token_version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "token_version": token_version,
        "role": role,
        "type": TokenType.ACCESS.value,
        "jti": secrets.token_hex(16),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> TokenPayload:
    """Verifies signature + expiry. Tries the current secret, then falls back
    to the previous secret (if configured) to support zero-downtime rotation."""
    secrets_to_try = [settings.JWT_SECRET_KEY]
    if settings.JWT_SECRET_KEY_PREVIOUS:
        secrets_to_try.append(settings.JWT_SECRET_KEY_PREVIOUS)

    last_error: Optional[Exception] = None
    for secret in secrets_to_try:
        try:
            raw = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
            payload = TokenPayload(**raw)
            if payload.type != TokenType.ACCESS.value:
                raise InvalidTokenError("Token is not an access token")
            return payload
        except (JWTError, ValidationError) as e:
            last_error = e
            continue
    raise InvalidTokenError(f"Could not validate token: {last_error}")


# ----------------------------------------------------------------------
# Opaque refresh tokens
# ----------------------------------------------------------------------
def generate_refresh_token() -> tuple[str, str]:
    """Returns (plaintext_token, sha256_hash). Only the hash is ever stored."""
    plaintext = secrets.token_urlsafe(64)
    token_hash = hash_token(plaintext)
    return plaintext, token_hash


def hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------
# Single-use opaque tokens (email verification / password reset)
# ----------------------------------------------------------------------
def generate_url_safe_token() -> str:
    return secrets.token_urlsafe(32)
