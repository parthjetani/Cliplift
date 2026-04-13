"""Generic TTL cache helper — Upstash Redis with in-memory fallback.

Extracted from the rate limiter pattern. Provides a single `cached()` function
for any async computation that should be memoized with a TTL.

Usage:
    result = await cached("analytics:overview:team-123", ttl=300, compute=fn)

Backend selection:
- If UPSTASH_REDIS_REST_URL is set → Upstash Redis REST API (production)
- Otherwise → in-process TTLCache (dev / single worker)

Fail-open: if Upstash is unreachable, falls through to recompute.
"""

import json
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx
from cachetools import TTLCache

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# In-process fallback cache (dev/single-worker only)
_local_cache: TTLCache[str, str] = TTLCache(maxsize=10_000, ttl=600)


async def cached(
    key: str,
    ttl_seconds: int,
    compute: Callable[[], Awaitable[T]],
    serialize: Callable[[T], str] = json.dumps,
    deserialize: Callable[[str], T] = json.loads,
) -> T:
    """Cache-aside wrapper for any async computation.

    Args:
        key: Cache key (should be unique per query + params)
        ttl_seconds: How long to cache the result
        compute: Async callable that produces the value if not cached
        serialize: How to turn the value into a string for storage
        deserialize: How to turn the stored string back into a value

    Returns:
        The cached or freshly-computed value
    """
    cached_value = await _get(key)
    if cached_value is not None:
        try:
            return deserialize(cached_value)
        except (json.JSONDecodeError, ValueError, TypeError):
            logger.warning(f"Cache deserialize failed for {key}, recomputing")

    result = await compute()

    try:
        serialized = serialize(result)
        await _set(key, serialized, ttl_seconds)
    except Exception as e:
        logger.warning(f"Cache write failed for {key}: {e}")

    return result


async def invalidate(key: str) -> None:
    """Remove a key from the cache."""
    _local_cache.pop(key, None)
    if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(
                    f"{settings.UPSTASH_REDIS_REST_URL}/del/{key}",
                    headers={"Authorization": f"Bearer {settings.UPSTASH_REDIS_REST_TOKEN}"},
                )
        except httpx.HTTPError:
            pass


async def _get(key: str) -> str | None:
    if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(
                    f"{settings.UPSTASH_REDIS_REST_URL}/get/{key}",
                    headers={"Authorization": f"Bearer {settings.UPSTASH_REDIS_REST_TOKEN}"},
                )
                response.raise_for_status()
                result = response.json().get("result")
                if result is not None:
                    return result
        except httpx.HTTPError as e:
            logger.debug(f"Upstash cache read failed: {e}")
    return _local_cache.get(key)


async def _set(key: str, value: str, ttl_seconds: int) -> None:
    _local_cache[key] = value
    if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(
                    f"{settings.UPSTASH_REDIS_REST_URL}/set/{key}/{value}",
                    headers={"Authorization": f"Bearer {settings.UPSTASH_REDIS_REST_TOKEN}"},
                    params={"EX": str(ttl_seconds)},
                )
        except httpx.HTTPError as e:
            logger.debug(f"Upstash cache write failed: {e}")
