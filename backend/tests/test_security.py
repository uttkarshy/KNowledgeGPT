import uuid

import pytest

from app.core.config import get_settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_round_trip():
    hashed = hash_password("SuperSecret123!")
    assert verify_password("SuperSecret123!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_round_trip():
    settings = get_settings()
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, role="user", settings=settings)
    payload = decode_access_token(token, settings)
    assert payload.sub == str(user_id)
    assert payload.role == "user"


def test_tampered_token_is_rejected():
    settings = get_settings()
    token = create_access_token(user_id=uuid.uuid4(), role="user", settings=settings)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token + "x", settings)


def test_refresh_token_hash_is_consistent():
    plaintext, digest = generate_refresh_token()
    assert hash_token(plaintext) == digest


def test_secret_rotation_fallback_accepts_old_secret():
    settings = get_settings()
    token = create_access_token(user_id=uuid.uuid4(), role="user", settings=settings)

    rotated_settings = settings.model_copy(
        update={"JWT_SECRET_KEY": "brand-new-secret", "JWT_SECRET_KEY_PREVIOUS": settings.JWT_SECRET_KEY}
    )
    payload = decode_access_token(token, rotated_settings)
    assert payload.sub is not None


def test_wrong_secret_is_rejected():
    settings = get_settings()
    token = create_access_token(user_id=uuid.uuid4(), role="user", settings=settings)

    wrong_settings = settings.model_copy(update={"JWT_SECRET_KEY": "totally-different-secret"})
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, wrong_settings)
