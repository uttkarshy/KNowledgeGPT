from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import _get_redis_client, rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    GoogleAuthCallbackRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserPublic,
    VerifyEmailRequest,
)
from app.services.auth import service as auth_service
from app.services.auth.google_oauth import GoogleOAuthError, exchange_code_for_userinfo

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_context(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(key_prefix="register", max_requests=3))],
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not settings.REGISTRATION_ENABLED:
        raise HTTPException(503, "New registrations are temporarily closed. Please contact support.")
    try:
        user = await auth_service.register_user(
            db, settings=settings, email=body.email, password=body.password, full_name=body.full_name
        )
    except auth_service.EmailAlreadyRegisteredError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(key_prefix="login", max_requests=5))],
)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        user = await auth_service.authenticate_user(db, email=body.email, password=body.password)
    except auth_service.InvalidCredentialsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    except auth_service.AccountSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    user_agent, ip_address = _client_context(request)
    pair = await auth_service.issue_token_pair(
        db, user=user, settings=settings, user_agent=user_agent, ip_address=ip_address
    )
    return TokenResponse(
        access_token=pair.access_token, refresh_token=pair.refresh_token, expires_in=pair.expires_in
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        pair = await auth_service.rotate_refresh_token(
            db,
            settings=settings,
            plaintext_refresh_token=body.refresh_token,
            **dict(zip(("user_agent", "ip_address"), _client_context(request), strict=True)),
        )
    except auth_service.InvalidOrExpiredTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    except auth_service.AccountSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    return TokenResponse(
        access_token=pair.access_token, refresh_token=pair.refresh_token, expires_in=pair.expires_in
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.revoke_refresh_token(db, plaintext_refresh_token=body.refresh_token)


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/verify-email", response_model=UserPublic)
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await auth_service.verify_email(db, token=body.token)
    except auth_service.InvalidOrExpiredTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/forgot-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit(key_prefix="forgot_password", max_requests=3))],
)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    # Always returns 204 regardless of whether the email exists, to avoid
    # leaking which addresses are registered.
    await auth_service.request_password_reset(db, settings=settings, email=body.email)


@router.post("/reset-password", response_model=UserPublic)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    try:
        return await auth_service.confirm_password_reset(
            db, token=body.token, new_password=body.new_password
        )
    except auth_service.InvalidOrExpiredTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/google/login", dependencies=[Depends(rate_limit(key_prefix="oauth", max_requests=5))])
async def google_login(response: Response, settings: Settings = Depends(get_settings)):
    if not settings.GOOGLE_OAUTH_ENABLED or not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Google sign-in is not configured. Use email and password.")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    await _get_redis_client(settings.REDIS_URL).set(f"oauth:{state}", verifier, ex=300)
    response.set_cookie("kgpt_oauth_state", state, httponly=True,
                        secure=settings.ENVIRONMENT == "production", samesite="lax", max_age=300,
                        path="/api/auth/google")
    params = urlencode({"client_id": settings.GOOGLE_CLIENT_ID, "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                        "response_type": "code", "scope": "openid email profile", "state": state,
                        "code_challenge": challenge, "code_challenge_method": "S256"})
    return {"authorization_url": f"https://accounts.google.com/o/oauth2/v2/auth?{params}"}


@router.post("/google/callback", response_model=TokenResponse)
async def google_callback(
    body: GoogleAuthCallbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not settings.GOOGLE_OAUTH_ENABLED:
        raise HTTPException(503, "Google sign-in is not configured")
    cookie_state = request.cookies.get("kgpt_oauth_state", "")
    if not body.state or not cookie_state or not secrets.compare_digest(body.state, cookie_state):
        raise HTTPException(400, "Invalid Google sign-in state. Start sign-in again.")
    verifier = await _get_redis_client(settings.REDIS_URL).getdel(f"oauth:{body.state}")
    if not verifier:
        raise HTTPException(400, "Google sign-in expired or was already used")
    try:
        google_info = await exchange_code_for_userinfo(code=body.code, settings=settings, code_verifier=verifier)
        user = await auth_service.get_or_create_google_user(db, google_info=google_info)
    except (GoogleOAuthError, auth_service.InvalidCredentialsError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except auth_service.AccountSuspendedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    user_agent, ip_address = _client_context(request)
    pair = await auth_service.issue_token_pair(
        db, user=user, settings=settings, user_agent=user_agent, ip_address=ip_address
    )
    return TokenResponse(
        access_token=pair.access_token, refresh_token=pair.refresh_token, expires_in=pair.expires_in
    )
