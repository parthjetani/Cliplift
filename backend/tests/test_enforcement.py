"""Tests for plan enforcement middleware — per-tier limits + cancellation + trial expiry.

Note: many tests make rapid sequential POST /creators/track calls. The route
has a rate_limit("track_creator", 20, 60) dependency that uses an in-memory
cache. In the full test suite, ALL test requests share the same ASGI transport
(no real client IP), so the rate limiter accumulates hits across test files.
The `_clear_rate_limits` fixture below resets the counter before each test in
this file to prevent cross-test pollution.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.auth.models import Team
from app.billing.mock import MockStripeClient
from app.database import AsyncSessionLocal, engine
from tests.test_creators import _create_real_user, authed_user  # noqa: F401


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear the in-memory rate-limit cache before each test.

    All test requests share the same ASGI transport (no real client IP), so
    the rate limiter accumulates hits across the entire test session. Without
    this, tests that make many POST /creators/track calls (which has a 20/min
    rate limit) collide with counts from other test files and return 429.
    """
    from app.common.ratelimit import _local_cache
    _local_cache.clear()


# ============================================================================
# Helpers
# ============================================================================


async def _get_team_id(client: AsyncClient, headers: dict) -> str:
    resp = await client.get("/api/v1/teams/me", headers=headers)
    return resp.json()["id"]


async def _set_team_plan(team_id: str, plan: str, **extra) -> None:
    """Directly update a team's plan (+ optional columns) via the DB."""
    async with AsyncSessionLocal() as s:
        values = {"plan": plan, **extra}
        await s.execute(
            update(Team).where(Team.id == uuid.UUID(team_id)).values(**values)
        )
        await s.commit()
    await engine.dispose()


async def _connect_youtube(client: AsyncClient, headers: dict) -> str:
    """Run the mock OAuth flow and return the connection_id."""
    auth_resp = await client.post(
        "/api/v1/connections/youtube/authorize", headers=headers
    )
    callback_url = auth_resp.json()["authorize_url"]
    parsed = urlparse(callback_url)
    await client.get(parsed.path + "?" + parsed.query, follow_redirects=False)
    list_resp = await client.get("/api/v1/connections", headers=headers)
    youtube_conns = [c for c in list_resp.json() if c["platform"] == "youtube"]
    return youtube_conns[-1]["id"]


# ============================================================================
# Creator tracking limits
# ============================================================================


class TestCreatorTrackingLimit:
    async def test_creator_tier_allows_3(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        for i in range(3):
            resp = await client.post(
                "/api/v1/creators/track",
                json={"platform": "youtube", "platform_id": f"limit-test-{uuid.uuid4().hex[:8]}"},
                headers=headers,
            )
            assert resp.status_code == 201, f"Track #{i+1} failed: {resp.text}"

    async def test_creator_tier_blocks_4th(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        for i in range(3):
            await client.post(
                "/api/v1/creators/track",
                json={"platform": "youtube", "platform_id": f"over-limit-{uuid.uuid4().hex[:8]}"},
                headers=headers,
            )
        resp = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": f"4th-{uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        assert resp.status_code == 402
        body = resp.json()
        assert body["error"]["code"] == "plan_limit_exceeded"
        assert body["error"]["details"]["limit_name"] == "tracked_creators"
        assert body["error"]["details"]["current_plan"] == "creator"
        assert body["error"]["details"]["suggested_plan"] == "team"

    async def test_team_tier_allows_more(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        team_id = await _get_team_id(client, headers)
        await _set_team_plan(team_id, "team")

        for i in range(5):
            resp = await client.post(
                "/api/v1/creators/track",
                json={"platform": "youtube", "platform_id": f"team-{uuid.uuid4().hex[:8]}"},
                headers=headers,
            )
            assert resp.status_code == 201, f"Track #{i+1} failed on team tier: {resp.text}"


# ============================================================================
# Platform connection limit (Creator = 1 platform)
# ============================================================================


class TestPlatformConnectionLimit:
    async def test_creator_first_connection_succeeds(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        resp = await client.post(
            "/api/v1/connections/youtube/authorize", headers=headers
        )
        assert resp.status_code == 200

    async def test_creator_second_connection_blocked(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        # First: connect YouTube
        await _connect_youtube(client, headers)

        # Second: try Instagram → 402
        resp = await client.post(
            "/api/v1/connections/instagram/authorize", headers=headers
        )
        assert resp.status_code == 402
        body = resp.json()
        assert body["error"]["details"]["limit_name"] == "max_platforms"
        assert body["error"]["details"]["suggested_plan"] == "team"

    async def test_team_tier_allows_multiple(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        team_id = await _get_team_id(client, headers)
        await _set_team_plan(team_id, "team")

        for platform in ["youtube", "instagram"]:
            resp = await client.post(
                f"/api/v1/connections/{platform}/authorize", headers=headers
            )
            assert resp.status_code == 200, f"{platform} connect failed on team tier"


# ============================================================================
# Scheduling disabled on Creator tier
# ============================================================================


class TestSchedulingDisabled:
    async def test_creator_presign_blocked(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        resp = await client.post(
            "/api/v1/publishing/uploads/presign",
            json={"filename": "test.mp4", "content_type": "video/mp4"},
            headers=headers,
        )
        assert resp.status_code == 402
        assert resp.json()["error"]["details"]["limit_name"] == "scheduling"

    async def test_creator_post_create_blocked(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        resp = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json={
                "connection_id": str(uuid.uuid4()),
                "platform": "youtube",
                "file_key": "x/y/z.mp4",
                "scheduled_for": datetime.now(timezone.utc).isoformat(),
            },
            headers=headers,
        )
        assert resp.status_code == 402
        assert resp.json()["error"]["details"]["limit_name"] == "scheduling"


# ============================================================================
# Cancelled team — hard cutoff (writes blocked, reads open)
# ============================================================================


class TestCancelledTeam:
    async def test_writes_blocked(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        team_id = await _get_team_id(client, headers)
        await _set_team_plan(team_id, "cancelled", trial_ends_at=None)

        # Track → 402
        resp = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": "blocked"},
            headers=headers,
        )
        assert resp.status_code == 402
        assert resp.json()["error"]["details"]["limit_name"] == "subscription_cancelled"

        # Niche create → 402
        resp = await client.post(
            "/api/v1/niches",
            json={"name": "blocked", "keywords": ["test"]},
            headers=headers,
        )
        assert resp.status_code == 402

    async def test_reads_still_work(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        team_id = await _get_team_id(client, headers)
        await _set_team_plan(team_id, "cancelled", trial_ends_at=None)

        # GET endpoints should still work
        resp = await client.get("/api/v1/creators", headers=headers)
        assert resp.status_code == 200

        resp = await client.get("/api/v1/niches", headers=headers)
        assert resp.status_code == 200

        resp = await client.get("/api/v1/teams/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["plan"] == "cancelled"

    async def test_connection_delete_still_works(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """Cancelled users can still disconnect OAuth connections (cleanup)."""
        _, _, headers = authed_user
        conn_id = await _connect_youtube(client, headers)

        team_id = await _get_team_id(client, headers)
        await _set_team_plan(team_id, "cancelled", trial_ends_at=None)

        resp = await client.delete(
            f"/api/v1/connections/{conn_id}", headers=headers
        )
        assert resp.status_code == 204

    async def test_reactivation_restores_writes(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        team_id = await _get_team_id(client, headers)

        # Cancel
        await _set_team_plan(team_id, "cancelled", trial_ends_at=None)

        # Verify blocked
        resp = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": "react-test"},
            headers=headers,
        )
        assert resp.status_code == 402

        # Reactivate via webhook
        sub_id, cus_id = f"sub_{uuid.uuid4().hex[:8]}", f"cus_{uuid.uuid4().hex[:8]}"
        event = MockStripeClient.build_synthetic_event(
            "checkout.session.completed",
            team_id=team_id,
            plan="team",
            subscription_id=sub_id,
            customer_id=cus_id,
        )
        await client.post(
            "/api/v1/billing/webhook",
            content=json.dumps(event),
            headers={"Stripe-Signature": "mock-signature", "Content-Type": "application/json"},
        )

        # Now writes work again
        resp = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": f"react-ok-{uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        assert resp.status_code == 201


# ============================================================================
# Trial expiry (never-paid users)
# ============================================================================


class TestTrialExpired:
    async def test_active_trial_allows_writes(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """Fresh user with trial in the future → writes pass."""
        _, _, headers = authed_user
        resp = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": f"trial-ok-{uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        assert resp.status_code == 201

    async def test_expired_trial_never_paid_blocks(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """Trial past + no subscription → 402 with limit_name=trial_expired."""
        _, _, headers = authed_user
        team_id = await _get_team_id(client, headers)
        await _set_team_plan(
            team_id, "creator",
            trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1),
            stripe_subscription_id=None,
        )

        resp = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": "expired"},
            headers=headers,
        )
        assert resp.status_code == 402
        assert resp.json()["error"]["details"]["limit_name"] == "trial_expired"

    async def test_expired_trial_but_paid_allows(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """Trial past + subscription exists → writes pass (trial gate only fires for never-paid)."""
        _, _, headers = authed_user
        team_id = await _get_team_id(client, headers)
        await _set_team_plan(
            team_id, "team",
            trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1),
            stripe_subscription_id=f"sub_{uuid.uuid4().hex[:8]}",
        )

        resp = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": f"paid-ok-{uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        assert resp.status_code == 201


# ============================================================================
# Cross-team isolation
# ============================================================================


class TestCrossTeamIsolation:
    async def test_one_teams_limit_doesnt_affect_another(
        self, client: AsyncClient
    ) -> None:
        """Team A at the creator cap shouldn't block Team B from tracking."""
        _, _, t1 = await _create_real_user()
        _, _, t2 = await _create_real_user()
        h1 = {"Authorization": f"Bearer {t1}"}
        h2 = {"Authorization": f"Bearer {t2}"}

        # Team A: fill up to limit
        for i in range(3):
            await client.post(
                "/api/v1/creators/track",
                json={"platform": "youtube", "platform_id": f"iso-a-{uuid.uuid4().hex[:8]}"},
                headers=h1,
            )

        # Team B: should still be able to track
        resp = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": f"iso-b-{uuid.uuid4().hex[:8]}"},
            headers=h2,
        )
        assert resp.status_code == 201
