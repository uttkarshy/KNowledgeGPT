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
from fastapi import Depends, HTTPException, Request

from app.core.config import Settings, get_settings


@lru_cache
def _get_redis_client(redis_url: str) -> redis.Redis:
    return redis.from_url(redis_url, decode_responses=True)


async def enforce_limit(settings: Settings, *, key: str, limit: int, seconds: int = 60) -> None:
    """Atomic expiry avoids immortal counters; fail closed for cost-bearing paths."""
    client = _get_redis_client(settings.REDIS_URL)
    try:
        current = await client.eval("""
            local n = redis.call('INCR', KEYS[1])
            if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
            return n
        """, 1, f"ratelimit:{key}", seconds)
    except redis.RedisError as exc:
        raise HTTPException(503, "Request limits are temporarily unavailable. Please retry.") from exc
    if current > limit:
        raise HTTPException(429, "Usage limit reached. Please try again later.", headers={"Retry-After": str(seconds)})


def rate_limit(*, key_prefix: str, max_requests: int, window_seconds: int = 60):
    """Dependency factory. Example:

        @router.post("/login", dependencies=[Depends(rate_limit(
            key_prefix="login", max_requests=settings.RATE_LIMIT_LOGIN_PER_MINUTE
        ))])
    """

    async def _enforce(request: Request, settings: Settings = Depends(get_settings)) -> None:
        client_ip = request.client.host if request.client else "unknown"
        await enforce_limit(settings, key=f"{key_prefix}:{client_ip}", limit=max_requests, seconds=window_seconds)

    return _enforce
