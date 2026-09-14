"""
API usage logging middleware.

Records one ApiUsageLog row per request: endpoint, status code, latency,
and the authenticated user if any. This is what feeds the admin analytics
dashboard and error dashboard — without it those would have nothing real
to show.

Deliberately best-effort: a logging failure (e.g. a transient DB hiccup)
must never break the actual request/response cycle, so all DB errors here
are caught and swallowed (with a warning logged) rather than propagated.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.usage import ApiUsageLog

logger = logging.getLogger(__name__)

# Endpoints excluded from logging — health checks would otherwise dominate
# the table with near-zero-value rows (hit every few seconds by the ALB).
_EXCLUDED_PATH_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")


def _extract_user_id(request: Request) -> uuid.UUID | None:
    """Best-effort extraction of the caller's user id from the bearer
    token, without raising — this is telemetry, not authentication; actual
    auth enforcement happens in the route's own dependencies."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):]
    try:
        settings = get_settings()
        payload = decode_access_token(token, settings)
        return uuid.UUID(payload.sub)
    except (InvalidTokenError, ValueError):
        return None


class ApiUsageLoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or any(
            scope["path"].startswith(p) for p in _EXCLUDED_PATH_PREFIXES
        ):
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500

        async def track_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        # Await the entire application, including streaming and yield-dependency
        # cleanup. Logging before cleanup can wait on a user-row FK lock held
        # by this very request, preventing its commit and exhausting the pool.
        await self.app(scope, receive, track_status)
        latency_ms = int((time.perf_counter() - start) * 1000)
        user_id = _extract_user_id(Request(scope))
        if user_id is not None:
            try:
                async with AsyncSessionLocal() as db:
                    db.add(
                        ApiUsageLog(
                            user_id=user_id,
                            endpoint=scope["path"],
                            latency_ms=latency_ms,
                            status_code=status_code,
                        )
                    )
                    await db.commit()
            except Exception as e:  # noqa: BLE001 - telemetry must never break the request
                logger.warning("Failed to record API usage log: %s", e)
