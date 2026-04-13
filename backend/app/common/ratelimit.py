"""Rate limiting with pluggable backend.

- If `UPSTASH_REDIS_REST_URL` is set → uses Upstash Redis (production-ready)
- Otherwise → uses in-memory TTLCache (dev / single-process fallback)

Usage as a FastAPI dependency:

    from app.common.ratelimit import rate_limit

    @router.post("/discover/search", dependencies=[Depends(rate_limit("search", 30, 60))])
    async def search(...): ...
"""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Annotated

import httpx
from cachetools import TTLCache
from fastapi import Depends, HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimitExceeded(HTTPException):
    """429 Too Many Requests."""

    def __init__(self, retry_after: int | None = None) -> None:
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please slow down.",
            headers=headers,
        )


# ----------------------------------------------------------------------------
# In-memory backend (dev / fallback)
# ----------------------------------------------------------------------------

# Per-process cache. NOT safe across multiple workers — fine for dev only.
_local_cache: TTLCache[str, list[float]] = TTLCache(maxsize=10000, ttl=3600)


def _local_check(key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
    """Sliding-window rate limit using an in-memory deque.

    Returns (allowed, retry_after_seconds).
    """
    now = time.time()
    window_start = now - window_seconds

    timestamps = _local_cache.get(key, [])
    # Drop entries outside the window
    timestamps = [t for t in timestamps if t > window_start]

    if len(timestamps) >= max_requests:
        # Rate limited — figure out when the oldest entry will fall out of the window
        retry_after = int(timestamps[0] + window_seconds - now) + 1
        _local_cache[key] = timestamps
        return False, max(retry_after, 1)

    timestamps.append(now)
    _local_cache[key] = timestamps
    return True, 0


# ----------------------------------------------------------------------------
# Upstash Redis backend (production)
# ----------------------------------------------------------------------------


async def _upstash_check(
    key: str, max_requests: int, window_seconds: int
) -> tuple[bool, int]:
    """Sliding-window rate limit via Upstash Redis REST API.

    Uses ZADD/ZREMRANGEBYSCORE/ZCARD pipeline. Returns (allowed, retry_after).
    """
    if not settings.UPSTASH_REDIS_REST_URL or not settings.UPSTASH_REDIS_REST_TOKEN:
        return _local_check(key, max_requests, window_seconds)

    now_ms = int(time.time() * 1000)
    window_start_ms = now_ms - (window_seconds * 1000)
    member = f"{now_ms}:{id(object())}"  # unique enough for sliding window

    headers = {"Authorization": f"Bearer {settings.UPSTASH_REDIS_REST_TOKEN}"}
    pipeline_url = f"{settings.UPSTASH_REDIS_REST_URL}/pipeline"

    # Pipelined: drop expired, add new, count, set TTL
    commands = [
        ["ZREMRANGEBYSCORE", key, "0", str(window_start_ms)],
        ["ZADD", key, str(now_ms), member],
        ["ZCARD", key],
        ["EXPIRE", key, str(window_seconds + 1)],
    ]

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(pipeline_url, headers=headers, json=commands)
            response.raise_for_status()
            results = response.json()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        # Fail open — better to serve a request than block on rate-limiter outage
        logger.warning(f"Upstash rate limit check failed, allowing request: {e}")
        return True, 0

    count = results[2].get("result", 0) if isinstance(results[2], dict) else results[2]
    if count > max_requests:
        return False, window_seconds
    return True, 0


# ----------------------------------------------------------------------------
# Public API: rate_limit dependency factory
# ----------------------------------------------------------------------------


def rate_limit(
    bucket: str,
    max_requests: int,
    window_seconds: int,
) -> Callable[..., Awaitable[None]]:
    """Build a FastAPI dependency that enforces a rate limit.

    Args:
        bucket: Logical name for this limit (e.g., "search", "publish")
        max_requests: Max requests allowed in the window
        window_seconds: Window size in seconds

    Example:
        @router.post(
            "/search",
            dependencies=[Depends(rate_limit("search", 30, 60))],
        )
        async def search(...): ...
    """

    async def _check(request: Request) -> None:
        # Use authenticated user ID if available, else fall back to client IP
        user_id = getattr(request.state, "user_id", None)
        identifier = user_id or (request.client.host if request.client else "unknown")
        key = f"ratelimit:{bucket}:{identifier}"

        allowed, retry_after = await _upstash_check(key, max_requests, window_seconds)
        if not allowed:
            raise RateLimitExceeded(retry_after=retry_after)

    return _check
