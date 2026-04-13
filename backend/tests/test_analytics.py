"""Integration tests for analytics endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from app.config import settings
from tests.test_creators import _create_real_user, authed_user  # noqa: F401


# ============================================================================
# Auth checks
# ============================================================================


class TestAnalyticsAuth:
    async def test_overview_requires_auth(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/analytics/overview")
        assert response.status_code == 401

    async def test_creator_timeline_requires_auth(self, client: AsyncClient) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/analytics/creators/{fake_id}/timeline")
        assert response.status_code == 401

    async def test_video_timeline_requires_auth(self, client: AsyncClient) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/analytics/videos/{fake_id}/timeline")
        assert response.status_code == 401

    async def test_niche_performance_requires_auth(self, client: AsyncClient) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/analytics/niches/{fake_id}/performance")
        assert response.status_code == 401

    async def test_recent_outliers_requires_auth(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/analytics/recent-outliers")
        assert response.status_code == 401


# ============================================================================
# Overview
# ============================================================================


class TestOverview:
    async def test_empty_overview_for_new_user(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.get("/api/v1/analytics/overview", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["tracked_creators"] == 0
        assert body["tracked_videos"] == 0
        assert body["active_niches"] == 0
        assert body["total_outliers"] == 0

    async def test_overview_counts_after_tracking(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user

        # Track a creator
        await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": f"analytics-test-{uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        # Create a niche
        await client.post(
            "/api/v1/niches",
            json={"name": "analytics test", "keywords": ["test"]},
            headers=headers,
        )

        # Invalidate cache to see fresh data
        from app.common.cache import _local_cache
        _local_cache.clear()

        response = await client.get("/api/v1/analytics/overview", headers=headers)
        body = response.json()
        assert body["tracked_creators"] >= 1
        assert body["active_niches"] >= 1


# ============================================================================
# Creator timeline
# ============================================================================


class TestCreatorTimeline:
    async def test_timeline_for_tracked_creator(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user

        # Track a creator
        track_resp = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": f"timeline-{uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        creator_id = track_resp.json()["creator"]["id"]

        response = await client.get(
            f"/api/v1/analytics/creators/{creator_id}/timeline?days=30",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["creator_id"] == creator_id
        assert body["days"] == 30
        assert isinstance(body["points"], list)

    async def test_timeline_404_for_untracked(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        fake_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/analytics/creators/{fake_id}/timeline",
            headers=headers,
        )
        assert response.status_code == 404


# ============================================================================
# Video timeline
# ============================================================================


class TestVideoTimeline:
    async def test_timeline_for_tracked_video(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user

        track_resp = await client.post(
            "/api/v1/videos/track",
            json={"platform": "youtube", "platform_video_id": f"vtimeline-{uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        video_id = track_resp.json()["video"]["id"]

        response = await client.get(
            f"/api/v1/analytics/videos/{video_id}/timeline?hours=72",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["video_id"] == video_id
        assert body["hours"] == 72
        assert isinstance(body["points"], list)
        # track_video creates an initial snapshot, so we should have at least 1 point
        assert len(body["points"]) >= 1

    async def test_timeline_404_for_untracked(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        fake_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/analytics/videos/{fake_id}/timeline",
            headers=headers,
        )
        assert response.status_code == 404


# ============================================================================
# Niche performance
# ============================================================================


class TestNichePerformance:
    async def test_performance_for_niche(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user

        niche_resp = await client.post(
            "/api/v1/niches",
            json={"name": "perf test", "keywords": ["performance"], "platforms": ["youtube"]},
            headers=headers,
        )
        niche_id = niche_resp.json()["id"]

        response = await client.get(
            f"/api/v1/analytics/niches/{niche_id}/performance?days=30",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["niche_id"] == niche_id
        assert body["days"] == 30
        assert isinstance(body["platform_breakdown"], list)
        assert isinstance(body["daily"], list)

    async def test_performance_404_for_wrong_team(
        self, client: AsyncClient
    ) -> None:
        u1_id, _, u1_token = await _create_real_user()
        u2_id, _, u2_token = await _create_real_user()
        h1 = {"Authorization": f"Bearer {u1_token}"}
        h2 = {"Authorization": f"Bearer {u2_token}"}

        niche_resp = await client.post(
            "/api/v1/niches",
            json={"name": "private", "keywords": ["p"]},
            headers=h1,
        )
        niche_id = niche_resp.json()["id"]

        # User 2 cannot get User 1's niche performance
        response = await client.get(
            f"/api/v1/analytics/niches/{niche_id}/performance",
            headers=h2,
        )
        assert response.status_code == 404


# ============================================================================
# Recent outliers
# ============================================================================


class TestRecentOutliers:
    async def test_empty_outliers_for_new_user(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.get(
            "/api/v1/analytics/recent-outliers",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_outliers_appear_after_worker(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user

        # Create a niche
        await client.post(
            "/api/v1/niches",
            json={"name": "outlier test", "keywords": ["fitness"], "platforms": ["youtube"]},
            headers=headers,
        )

        # Run discover-trends worker to populate niche_videos
        dev_headers = {"X-Dev-Worker-Token": settings.ENCRYPTION_KEY}
        await client.post(
            "/api/v1/workers/discover-trends?max_age_hours=0",
            headers=dev_headers,
        )

        # Clear cache
        from app.common.cache import _local_cache
        _local_cache.clear()

        response = await client.get(
            "/api/v1/analytics/recent-outliers?limit=5",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        # Mock provider injects outliers (Z >= 3.0), so we should have at least 1
        assert body["total"] >= 1
        first = body["items"][0]
        assert "niche_name" in first
        assert "outlier_score" in first
        assert first["outlier_score"] >= 3.0
        assert "video_id" in first
        assert "platform" in first
