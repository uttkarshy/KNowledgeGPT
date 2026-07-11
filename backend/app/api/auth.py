from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import rate_limit
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
            **dict(zip(("user_agent", "ip_address"), _client_context(request))),
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


@router.get("/google/login")
async def google_login(settings: Settings = Depends(get_settings)):
    """Returns the URL the frontend should redirect the user to."""
    params = (
        f"client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
        "&prompt=consent"
    )
    return {"authorization_url": f"https://accounts.google.com/o/oauth2/v2/auth?{params}"}


@router.post("/google/callback", response_model=TokenResponse)
async def google_callback(
    body: GoogleAuthCallbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        google_info = await exchange_code_for_userinfo(code=body.code, settings=settings)
        user = await auth_service.get_or_create_google_user(db, google_info=google_info)
    except GoogleOAuthError as e:
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
