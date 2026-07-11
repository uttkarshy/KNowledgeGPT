"""
Redis-backed rate limiting.

A fixed-window counter (simple, cheap, sufficient for auth endpoints) keyed
by client IP + route. Not a sliding-log limiter — acceptable tradeoff for
login/register/password-reset, where the goal is blunting brute force and
credential stuffing, not perfect precision.
"""

from __future__ import annotations

from functools import lru_cache

import redis.asyncio as redis
from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings


@lru_cache
def _get_redis_client(redis_url: str) -> redis.Redis:
    return redis.from_url(redis_url, decode_responses=True)


def rate_limit(*, key_prefix: str, max_requests: int, window_seconds: int = 60):
    """Dependency factory. Example:

        @router.post("/login", dependencies=[Depends(rate_limit(
            key_prefix="login", max_requests=settings.RATE_LIMIT_LOGIN_PER_MINUTE
        ))])
    """

    async def _enforce(request: Request, settings: Settings = Depends(get_settings)) -> None:
        client_ip = request.client.host if request.client else "unknown"
        redis_key = f"ratelimit:{key_prefix}:{client_ip}"
        client = _get_redis_client(settings.REDIS_URL)

        try:
            current = await client.incr(redis_key)
            if current == 1:
                await client.expire(redis_key, window_seconds)
        except redis.RedisError:
            # Fail OPEN rather than taking down auth entirely if Redis is
            # unavailable — logged elsewhere via app-wide error tracking.
            return

        if current > max_requests:
            ttl = await client.ttl(redis_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again shortly.",
                headers={"Retry-After": str(max(ttl, 1))},
            )

    return _enforce
