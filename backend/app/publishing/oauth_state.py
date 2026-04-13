"""OAuth state storage with TTL.

The OAuth `state` parameter binds a callback to the user/team that initiated
the flow — prevents CSRF and lets us know which team to attach the connection to.

Backend pluggable:
- Upstash Redis when UPSTASH_REDIS_REST_URL is configured
- In-process TTLCache fallback for dev (10 minute TTL)
"""

import json
import logging
import secrets
import uuid
from typing import Any

import httpx
from cachetools import TTLCache

from app.config import settings

logger = logging.getLogger(__name__)

STATE_TTL_SECONDS = 600  # 10 minutes — OAuth flows must complete within this window

# In-process fallback (dev only — not safe across multiple workers)
_local_state: TTLCache[str, str] = TTLCache(maxsize=10000, ttl=STATE_TTL_SECONDS)


def generate_state() -> str:
    """Cryptographically random state token (URL-safe)."""
    return secrets.token_urlsafe(32)


async def store_state(state: str, payload: dict[str, Any]) -> None:
    """Persist a state → payload mapping for STATE_TTL_SECONDS."""
    serialized = json.dumps(payload, default=str)

    if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
        try:
            async with httpx.AsyncClient(timeout=2.0) as http:
                response = await http.post(
                    f"{settings.UPSTASH_REDIS_REST_URL}/set/oauth_state:{state}",
                    headers={
                        "Authorization": f"Bearer {settings.UPSTASH_REDIS_REST_TOKEN}"
                    },
                    json={"value": serialized, "EX": STATE_TTL_SECONDS},
                )
                response.raise_for_status()
                return
        except httpx.HTTPError as e:
            logger.warning(f"Upstash state store failed, using local fallback: {e}")

    _local_state[state] = serialized


async def retrieve_state(state: str) -> dict[str, Any] | None:
    """Fetch and DELETE the state (single-use)."""
    if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
        try:
            async with httpx.AsyncClient(timeout=2.0) as http:
                # GET + DEL pipeline
                pipe = await http.post(
                    f"{settings.UPSTASH_REDIS_REST_URL}/pipeline",
                    headers={
                        "Authorization": f"Bearer {settings.UPSTASH_REDIS_REST_TOKEN}"
                    },
                    json=[
                        ["GET", f"oauth_state:{state}"],
                        ["DEL", f"oauth_state:{state}"],
                    ],
                )
                pipe.raise_for_status()
                results = pipe.json()
                value = results[0].get("result") if isinstance(results[0], dict) else results[0]
                if value:
                    return json.loads(value)
        except httpx.HTTPError as e:
            logger.warning(f"Upstash state fetch failed: {e}")

    serialized = _local_state.pop(state, None)
    if serialized:
        return json.loads(serialized)
    return None
