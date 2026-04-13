"""Integration tests for creators endpoints (per-team tracking).

These tests require:
- The local Supabase Postgres running (via `npx supabase start`)
- A user row in auth.users (created via Supabase signup)

The test fixture creates a fresh user via the Supabase REST API for each test.
"""

import os
import time
import uuid

import httpx
import jwt
import pytest
from httpx import AsyncClient

from app.config import settings


SUPABASE_URL = "http://127.0.0.1:54321"
SUPABASE_ANON_KEY = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"


def make_test_jwt(user_id: str, email: str = "test@cliplift.com") -> str:
    """Forge a valid HS256 JWT signed with the local Supabase JWT secret.

    This works because the local Supabase JWT secret is the default
    'super-secret-jwt-token-with-at-least-32-characters-long' and our middleware
    accepts both HS256 and ES256.

    For tests that need a real auth.users row (so the profile FK works), use
    `_create_real_user()` instead which signs up via the Supabase REST API.
    """
    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


async def _create_real_user() -> tuple[str, str, str]:
    """Sign up a real user via Supabase Auth REST API. Returns (user_id, email, token)."""
    email = f"test+{int(time.time() * 1000)}+{uuid.uuid4().hex[:6]}@cliplift.com"
    password = "TestPassword123!"
    async with httpx.AsyncClient() as http:
        response = await http.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            json={"email": email, "password": password},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
    return data["user"]["id"], email, data["access_token"]


@pytest.fixture
async def authed_user() -> tuple[str, str, dict]:
    """Create a real Supabase user and return (user_id, email, headers)."""
    user_id, email, token = await _create_real_user()
    return user_id, email, {"Authorization": f"Bearer {token}"}


async def _upgrade_team_plan(
    client, headers: dict, plan: str = "team"
) -> str:
    """Upgrade the authenticated user's team to a given plan via the DB.

    Needed because plan enforcement (Chunk 24) blocks scheduling and multi-
    platform connections on the Creator tier. Tests that existed before
    enforcement was wired in need to upgrade to "team" to keep working.

    Returns the team_id.
    """
    from sqlalchemy import update as sa_update
    from app.auth.models import Team
    from app.database import AsyncSessionLocal, engine

    # Resolve team_id via the API
    resp = await client.get("/api/v1/teams/me", headers=headers)
    team_id = resp.json()["id"]

    async with AsyncSessionLocal() as s:
        await s.execute(
            sa_update(Team)
            .where(Team.id == __import__("uuid").UUID(team_id))
            .values(plan=plan)
        )
        await s.commit()
    await engine.dispose()
    return team_id


# ============================================================================
# Auth checks
# ============================================================================


class TestCreatorsAuth:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/creators")
        assert response.status_code == 401

    async def test_track_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": "abc"},
        )
        assert response.status_code == 401

    async def test_untrack_requires_auth(self, client: AsyncClient) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/creators/{fake_id}/untrack")
        assert response.status_code == 401


# ============================================================================
# List
# ============================================================================


class TestListCreators:
    async def test_empty_list_for_new_user(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.get("/api/v1/creators", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["has_more"] is False
        assert body["next_cursor"] is None


# ============================================================================
# Track
# ============================================================================


class TestTrackCreator:
    async def test_track_with_explicit_platform(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/creators/track",
            json={
                "platform": "youtube",
                "platform_id": "test-creator-explicit",
                "notes": "watching for inspiration",
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["creator"]["platform"] == "youtube"
        assert body["creator"]["platform_id"] == "test-creator-explicit"
        assert body["notes"] == "watching for inspiration"

    async def test_track_idempotent(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        body = {"platform": "youtube", "platform_id": "test-creator-idem"}
        a = await client.post("/api/v1/creators/track", json=body, headers=headers)
        b = await client.post("/api/v1/creators/track", json=body, headers=headers)
        assert a.status_code == 201
        assert b.status_code == 201
        # Same tracking row returned (same id)
        assert a.json()["id"] == b.json()["id"]

    async def test_track_via_url(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/creators/track",
            json={"url": "https://youtube.com/@testcreator"},
            headers=headers,
        )
        assert response.status_code == 201
        assert response.json()["creator"]["platform"] == "youtube"

    async def test_track_missing_fields_returns_422(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/creators/track",
            json={},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_track_then_list_shows_creator(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        await client.post(
            "/api/v1/creators/track",
            json={"platform": "tiktok", "platform_id": "test-list-flow"},
            headers=headers,
        )
        list_response = await client.get("/api/v1/creators", headers=headers)
        assert list_response.status_code == 200
        items = list_response.json()["items"]
        assert len(items) == 1
        assert items[0]["creator"]["platform_id"] == "test-list-flow"

    async def test_plan_limit_enforced(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        # Default plan = creator, max_tracked_creators = 3
        for i in range(3):
            r = await client.post(
                "/api/v1/creators/track",
                json={"platform": "youtube", "platform_id": f"limit-test-{i}"},
                headers=headers,
            )
            assert r.status_code == 201

        # 4th creator should hit the limit
        over = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": "limit-test-OVER"},
            headers=headers,
        )
        assert over.status_code == 402
        body = over.json()
        # The error envelope wraps it; FastAPI HTTPException with dict detail
        # gets wrapped by our error handler
        assert "plan_limit" in str(body).lower() or over.json()["error"]["code"] == "error"


# ============================================================================
# Untrack
# ============================================================================


class TestUntrackCreator:
    async def test_untrack_removes_from_list(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        track_resp = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": "untrack-test"},
            headers=headers,
        )
        assert track_resp.status_code == 201
        creator_id = track_resp.json()["creator"]["id"]

        untrack_resp = await client.delete(
            f"/api/v1/creators/{creator_id}/untrack",
            headers=headers,
        )
        assert untrack_resp.status_code == 204

        list_resp = await client.get("/api/v1/creators", headers=headers)
        assert list_resp.json()["items"] == []

    async def test_untrack_not_tracked_returns_404(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        fake_id = str(uuid.uuid4())
        response = await client.delete(
            f"/api/v1/creators/{fake_id}/untrack",
            headers=headers,
        )
        assert response.status_code == 404


# ============================================================================
# Detail
# ============================================================================


class TestCreatorDetail:
    async def test_get_tracked_creator_detail(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        # Unique platform_id per test run so snapshots from prior runs don't pollute
        unique_id = f"detail-test-{uuid.uuid4().hex[:8]}"
        track_resp = await client.post(
            "/api/v1/creators/track",
            json={"platform": "linkedin", "platform_id": unique_id},
            headers=headers,
        )
        creator_id = track_resp.json()["creator"]["id"]

        detail = await client.get(f"/api/v1/creators/{creator_id}", headers=headers)
        assert detail.status_code == 200
        body = detail.json()
        assert body["creator"]["id"] == creator_id
        assert body["tracking"] is not None
        # recent_snapshots may be 0 (no worker ran) or N (worker ran in same suite)
        assert isinstance(body["recent_snapshots"], list)

    async def test_get_unknown_creator_returns_404(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/creators/{fake_id}", headers=headers)
        assert response.status_code == 404


# ============================================================================
# Cross-team isolation
# ============================================================================


class TestCrossTeamIsolation:
    async def test_user2_does_not_see_user1_creators(
        self, client: AsyncClient
    ) -> None:
        _, _, headers1 = (await _create_real_user(),)[0][0], (await _create_real_user(),)[0][1], None
        # Easier: create two separate users
        u1_id, u1_email, u1_token = await _create_real_user()
        u2_id, u2_email, u2_token = await _create_real_user()
        h1 = {"Authorization": f"Bearer {u1_token}"}
        h2 = {"Authorization": f"Bearer {u2_token}"}

        await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": "isolation-test"},
            headers=h1,
        )

        # User 2 should see an empty list
        u2_list = await client.get("/api/v1/creators", headers=h2)
        assert u2_list.json()["items"] == []

        # User 1 still sees their tracked creator
        u1_list = await client.get("/api/v1/creators", headers=h1)
        assert len(u1_list.json()["items"]) == 1
