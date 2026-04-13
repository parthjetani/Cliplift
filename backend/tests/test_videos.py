"""Integration tests for video tracking endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from tests.test_creators import _create_real_user, authed_user  # noqa: F401


# ============================================================================
# Auth checks
# ============================================================================


class TestVideosAuth:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/videos")
        assert response.status_code == 401

    async def test_track_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/videos/track",
            json={"platform": "youtube", "platform_video_id": "abc"},
        )
        assert response.status_code == 401


# ============================================================================
# Track + list
# ============================================================================


class TestVideoTracking:
    async def test_empty_list_for_new_user(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.get("/api/v1/videos", headers=headers)
        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_track_video_explicit(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/videos/track",
            json={"platform": "youtube", "platform_video_id": "video-test-1"},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["video"]["platform"] == "youtube"
        assert body["video"]["platform_video_id"] == "video-test-1"
        # Mock provider returns view counts > 0
        assert body["video"]["latest_views"] >= 0

    async def test_track_via_url_youtube_shorts(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/videos/track",
            json={"url": "https://youtube.com/shorts/abc123XYZ"},
            headers=headers,
        )
        assert response.status_code == 201
        assert response.json()["video"]["platform"] == "youtube"
        assert response.json()["video"]["platform_video_id"] == "abc123xyz"

    async def test_track_idempotent(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        body = {"platform": "tiktok", "platform_video_id": "video-idem"}
        a = await client.post("/api/v1/videos/track", json=body, headers=headers)
        b = await client.post("/api/v1/videos/track", json=body, headers=headers)
        assert a.status_code == 201
        assert b.status_code == 201
        assert a.json()["id"] == b.json()["id"]

    async def test_track_then_list(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        await client.post(
            "/api/v1/videos/track",
            json={"platform": "linkedin", "platform_video_id": "video-list"},
            headers=headers,
        )
        list_response = await client.get("/api/v1/videos", headers=headers)
        items = list_response.json()["items"]
        assert len(items) == 1
        assert items[0]["video"]["platform_video_id"] == "video-list"

    async def test_track_missing_fields(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/videos/track",
            json={},
            headers=headers,
        )
        assert response.status_code == 422


# ============================================================================
# Untrack
# ============================================================================


class TestUntrackVideo:
    async def test_untrack_removes_from_list(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        track_resp = await client.post(
            "/api/v1/videos/track",
            json={"platform": "instagram", "platform_video_id": "untrack-vid"},
            headers=headers,
        )
        video_id = track_resp.json()["video"]["id"]

        untrack_resp = await client.delete(
            f"/api/v1/videos/{video_id}/untrack",
            headers=headers,
        )
        assert untrack_resp.status_code == 204

        list_resp = await client.get("/api/v1/videos", headers=headers)
        assert list_resp.json()["items"] == []

    async def test_untrack_not_tracked_returns_404(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        fake_id = str(uuid.uuid4())
        response = await client.delete(
            f"/api/v1/videos/{fake_id}/untrack",
            headers=headers,
        )
        assert response.status_code == 404


# ============================================================================
# Detail
# ============================================================================


class TestVideoDetail:
    async def test_get_video_detail_includes_first_snapshot(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        track_resp = await client.post(
            "/api/v1/videos/track",
            json={"platform": "youtube", "platform_video_id": "detail-vid"},
            headers=headers,
        )
        video_id = track_resp.json()["video"]["id"]

        detail = await client.get(f"/api/v1/videos/{video_id}", headers=headers)
        assert detail.status_code == 200
        body = detail.json()
        assert body["video"]["id"] == video_id
        assert body["tracking"] is not None
        # track_video creates an initial snapshot
        assert len(body["recent_snapshots"]) >= 1

    async def test_get_unknown_video_returns_404(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/videos/{fake_id}", headers=headers)
        assert response.status_code == 404
