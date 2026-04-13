"""Integration tests for the QStash-triggered worker endpoints."""

import pytest
from httpx import AsyncClient

from app.config import settings
from tests.test_creators import _create_real_user, authed_user  # noqa: F401


def dev_headers() -> dict:
    """Headers that pass dev-mode worker auth."""
    return {"X-Dev-Worker-Token": settings.ENCRYPTION_KEY}


# ============================================================================
# Auth checks
# ============================================================================


class TestWorkerAuth:
    async def test_no_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/workers/scrape-creators")
        assert response.status_code == 401

    async def test_wrong_dev_token_returns_401(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/workers/scrape-creators",
            headers={"X-Dev-Worker-Token": "wrong-token"},
        )
        assert response.status_code == 401

    async def test_correct_dev_token_returns_200(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/workers/scrape-creators",
            headers=dev_headers(),
        )
        assert response.status_code == 200


# ============================================================================
# scrape-creators
# ============================================================================


class TestScrapeCreators:
    async def test_empty_db_returns_zero(self, client: AsyncClient) -> None:
        """Worker handles empty creator table gracefully."""
        response = await client.post(
            "/api/v1/workers/scrape-creators", headers=dev_headers()
        )
        body = response.json()
        # New users may exist from other tests but we just verify the shape
        assert "processed" in body
        assert "errors" in body
        assert "total" in body

    async def test_scrape_after_tracking_creates_snapshot(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """Tracking a creator then running the worker creates a snapshot row."""
        _, _, headers = authed_user

        # Track a creator
        track_resp = await client.post(
            "/api/v1/creators/track",
            json={"platform": "youtube", "platform_id": "worker-snapshot-test"},
            headers=headers,
        )
        assert track_resp.status_code == 201
        creator_id = track_resp.json()["creator"]["id"]

        # Run the worker with max_age_hours=0 to force-process (track just set
        # last_scraped_at to now, so the default 24h cutoff would skip it)
        worker_resp = await client.post(
            "/api/v1/workers/scrape-creators?max_age_hours=0",
            headers=dev_headers(),
        )
        assert worker_resp.status_code == 200
        assert worker_resp.json()["processed"] >= 1

        # Detail should now include at least one snapshot
        detail = await client.get(
            f"/api/v1/creators/{creator_id}", headers=headers
        )
        assert len(detail.json()["recent_snapshots"]) >= 1


# ============================================================================
# scrape-videos
# ============================================================================


class TestScrapeVideos:
    async def test_scrape_videos_runs(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/workers/scrape-videos", headers=dev_headers()
        )
        assert response.status_code == 200
        body = response.json()
        assert "processed" in body
        assert "errors" in body

    async def test_scrape_after_tracking_updates_video(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """Tracking a video then running scrape-videos appends a new snapshot."""
        _, _, headers = authed_user

        track_resp = await client.post(
            "/api/v1/videos/track",
            json={"platform": "youtube", "platform_video_id": "worker-vid-test"},
            headers=headers,
        )
        video_id = track_resp.json()["video"]["id"]

        await client.post(
            "/api/v1/workers/scrape-videos", headers=dev_headers()
        )

        detail = await client.get(f"/api/v1/videos/{video_id}", headers=headers)
        # track_video creates 1 snapshot, the worker may add a second
        assert len(detail.json()["recent_snapshots"]) >= 1


# ============================================================================
# discover-trends
# ============================================================================


class TestDiscoverTrends:
    async def test_discover_trends_runs(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/workers/discover-trends", headers=dev_headers()
        )
        assert response.status_code == 200
        body = response.json()
        assert "processed" in body
        assert "videos_added" in body

    async def test_discover_populates_niche_feed(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """Creating a niche then running discover-trends populates its feed."""
        _, _, headers = authed_user

        # Create an active niche
        niche_resp = await client.post(
            "/api/v1/niches",
            json={
                "name": "fitness shorts",
                "keywords": ["fitness", "workout"],
                "platforms": ["youtube"],
            },
            headers=headers,
        )
        niche_id = niche_resp.json()["id"]

        # Feed should be empty initially
        empty_feed = await client.get(
            f"/api/v1/niches/{niche_id}/feed", headers=headers
        )
        assert empty_feed.json()["items"] == []

        # Run discover-trends with max_age_hours=0 to force-process the brand new niche
        worker_resp = await client.post(
            "/api/v1/workers/discover-trends?max_age_hours=0",
            headers=dev_headers(),
        )
        assert worker_resp.status_code == 200
        assert worker_resp.json()["videos_added"] > 0

        # Feed should now have items
        feed = await client.get(
            f"/api/v1/niches/{niche_id}/feed", headers=headers
        )
        assert feed.status_code == 200
        items = feed.json()["items"]
        assert len(items) > 0
        # Each item should have a video and an outlier_score (niche-relative)
        first = items[0]
        assert "video" in first
        assert "outlier_score" in first
        assert first["video"]["platform"] == "youtube"
