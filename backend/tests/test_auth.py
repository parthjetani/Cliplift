"""Tests for Supabase JWT validation and profile endpoints."""

import time
import uuid

import jwt
import pytest
from httpx import AsyncClient

from app.config import settings


def make_test_jwt(
    user_id: str | None = None,
    email: str = "test@example.com",
    expires_in_seconds: int = 3600,
    audience: str = "authenticated",
) -> str:
    """Forge a Supabase-shaped JWT for testing.

    Uses the same secret + algorithm Supabase does, so our middleware accepts it.
    """
    now = int(time.time())
    payload = {
        "sub": user_id or str(uuid.uuid4()),
        "email": email,
        "aud": audience,
        "role": "authenticated",
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


# ----------------------------------------------------------------------------
# JWT validation
# ----------------------------------------------------------------------------


async def test_profile_requires_auth(client: AsyncClient) -> None:
    """GET /profile without Authorization header → 401."""
    response = await client.get("/api/v1/profile")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"


async def test_profile_rejects_malformed_header(client: AsyncClient) -> None:
    """Bad Authorization header format → 401."""
    response = await client.get(
        "/api/v1/profile",
        headers={"Authorization": "NotBearer xyz"},
    )
    assert response.status_code == 401


async def test_profile_rejects_invalid_jwt(client: AsyncClient) -> None:
    """Invalid JWT signature → 401."""
    response = await client.get(
        "/api/v1/profile",
        headers={"Authorization": "Bearer not.a.real.jwt"},
    )
    assert response.status_code == 401


async def test_profile_rejects_expired_jwt(client: AsyncClient) -> None:
    """Expired JWT → 401."""
    expired_token = make_test_jwt(expires_in_seconds=-60)
    response = await client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["error"]["message"].lower()


async def test_profile_rejects_wrong_audience(client: AsyncClient) -> None:
    """JWT with wrong audience → 401."""
    bad_aud_token = make_test_jwt(audience="not-authenticated")
    response = await client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {bad_aud_token}"},
    )
    assert response.status_code == 401


# ----------------------------------------------------------------------------
# Error format consistency
# ----------------------------------------------------------------------------


async def test_error_envelope_shape(client: AsyncClient) -> None:
    """All errors should follow {error: {code, message}} shape."""
    response = await client.get("/api/v1/profile")
    body = response.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
