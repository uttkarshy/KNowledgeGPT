"""
Google OAuth 2.0 authorization-code exchange.

Isolated in its own module (mirrors the LLM provider pattern): if the app
ever needs another OAuth provider (Microsoft, GitHub, ...), it gets its own
sibling module implementing the same two functions, and auth/service.py
doesn't change.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from app.core.config import Settings

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleOAuthError(Exception):
    pass


class GoogleUserInfo(BaseModel):
    sub: str  # Google's stable user id
    email: str
    email_verified: bool = False
    name: str | None = None


async def exchange_code_for_userinfo(
    *, code: str, settings: Settings
) -> GoogleUserInfo:
    """Exchanges an authorization code for tokens, then fetches the user's
    profile. Raises GoogleOAuthError on any failure — callers never see
    httpx-specific exceptions."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise GoogleOAuthError("Google OAuth is not configured on this server")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]

            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
            data = userinfo_response.json()
        except httpx.HTTPStatusError as e:
            raise GoogleOAuthError(f"Google OAuth request failed: {e}") from e
        except httpx.RequestError as e:
            raise GoogleOAuthError(f"Could not reach Google OAuth endpoints: {e}") from e
        except (KeyError, ValueError) as e:
            raise GoogleOAuthError(f"Unexpected Google OAuth response shape: {e}") from e

    return GoogleUserInfo(
        sub=data["sub"],
        email=data["email"],
        email_verified=data.get("email_verified", False),
        name=data.get("name"),
    )
