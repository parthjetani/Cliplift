"""Tests for AI content brief generation."""

import uuid

import pytest
from httpx import AsyncClient

from app.ai.mock import MockAIClient
from app.ai.schemas import ContentBrief
from app.config import settings
from app.platforms.base import Platform, VideoSearchResult
from tests.test_creators import _create_real_user, authed_user  # noqa: F401


def _make_video(title: str = "Test video about fitness") -> VideoSearchResult:
    return VideoSearchResult(
        platform=Platform.YOUTUBE,
        platform_video_id="test-vid-123",
        url="https://youtube.com/shorts/test",
        title=title,
        creator_username="testcreator",
        views=100_000,
        likes=5000,
        comments=200,
        shares=50,
        engagement_rate=0.052,
        hashtags=["fitness", "workout", "shorts"],
    )


# ============================================================================
# MockAIClient unit tests
# ============================================================================


class TestMockAIClient:
    async def test_returns_content_brief(self) -> None:
        client = MockAIClient()
        brief = await client.generate_content_brief(_make_video())
        assert isinstance(brief, ContentBrief)
        assert brief.hook_analysis  # non-empty
        assert brief.format
        assert brief.suggested_hook
        assert brief.suggested_caption
        assert len(brief.suggested_hashtags) >= 3
        assert brief.cta

    async def test_deterministic(self) -> None:
        """Same video title → same brief."""
        client = MockAIClient()
        a = await client.generate_content_brief(_make_video("fitness hooks"))
        b = await client.generate_content_brief(_make_video("fitness hooks"))
        assert a.hook_analysis == b.hook_analysis
        assert a.suggested_hook == b.suggested_hook

    async def test_different_titles_different_briefs(self) -> None:
        client = MockAIClient()
        a = await client.generate_content_brief(_make_video("fitness hooks"))
        b = await client.generate_content_brief(_make_video("cooking tips"))
        # At least one field should differ
        assert a.hook_analysis != b.hook_analysis or a.format != b.format

    async def test_terse_output(self) -> None:
        """Mock output should be short (matching Haiku tone), not essay-length."""
        client = MockAIClient()
        brief = await client.generate_content_brief(_make_video())
        # Each field should be under 200 chars (Haiku-terse)
        assert len(brief.hook_analysis) < 200
        assert len(brief.format) < 200
        assert len(brief.suggested_hook) < 200
        assert len(brief.suggested_caption) < 300
        assert len(brief.cta) < 100

    async def test_hashtags_include_video_tags(self) -> None:
        """Mock should incorporate the video's existing hashtags."""
        client = MockAIClient()
        brief = await client.generate_content_brief(
            _make_video("test")
        )
        # Should include at least one of the original hashtags
        original = {"fitness", "workout", "shorts"}
        overlap = set(brief.suggested_hashtags) & original
        assert len(overlap) >= 1


# ============================================================================
# /api/v1/discover/generate-idea endpoint tests
# ============================================================================


class TestGenerateIdeaEndpoint:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/discover/generate-idea",
            json={"video_id": str(uuid.uuid4())},
        )
        assert response.status_code == 401

    async def test_404_for_unknown_video(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/discover/generate-idea",
            json={"video_id": str(uuid.uuid4())},
            headers=headers,
        )
        assert response.status_code == 404

    async def test_generates_brief_for_tracked_video(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user

        # Track a video so it exists in the DB
        track_resp = await client.post(
            "/api/v1/videos/track",
            json={"platform": "youtube", "platform_video_id": f"ai-test-{uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        assert track_resp.status_code == 201
        video_id = track_resp.json()["video"]["id"]

        # Generate idea
        response = await client.post(
            "/api/v1/discover/generate-idea",
            json={"video_id": video_id},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["video_id"] == video_id
        assert "brief" in body
        brief = body["brief"]
        assert brief["hook_analysis"]
        assert brief["format"]
        assert brief["suggested_hook"]
        assert brief["suggested_caption"]
        assert isinstance(brief["suggested_hashtags"], list)
        assert brief["cta"]
        assert "generated_at" in brief

    async def test_cached_on_second_call(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user

        track_resp = await client.post(
            "/api/v1/videos/track",
            json={"platform": "tiktok", "platform_video_id": f"cache-test-{uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        video_id = track_resp.json()["video"]["id"]

        # First call
        r1 = await client.post(
            "/api/v1/discover/generate-idea",
            json={"video_id": video_id},
            headers=headers,
        )
        # Second call — should hit cache
        r2 = await client.post(
            "/api/v1/discover/generate-idea",
            json={"video_id": video_id},
            headers=headers,
        )

        assert r1.status_code == 200
        assert r2.status_code == 200
        # Both should return the same brief content
        assert r1.json()["brief"]["hook_analysis"] == r2.json()["brief"]["hook_analysis"]

    async def test_niche_discovered_video_works(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """Videos from niche discovery (not explicitly tracked) should also work."""
        _, _, headers = authed_user

        # Create a niche and populate via worker
        await client.post(
            "/api/v1/niches",
            json={"name": "ai test niche", "keywords": ["ai"], "platforms": ["youtube"]},
            headers=headers,
        )
        dev_headers = {"X-Dev-Worker-Token": settings.ENCRYPTION_KEY}
        await client.post(
            "/api/v1/workers/discover-trends?max_age_hours=0",
            headers=dev_headers,
        )

        # Get the niche feed to find a video
        niche_list = await client.get("/api/v1/niches", headers=headers)
        niche_id = niche_list.json()["items"][0]["id"]
        feed = await client.get(
            f"/api/v1/niches/{niche_id}/feed?limit=1",
            headers=headers,
        )
        items = feed.json()["items"]
        if not items:
            pytest.skip("No videos discovered (edge case)")

        video_id = items[0]["video"]["id"]

        # Generate idea for a niche-discovered video
        response = await client.post(
            "/api/v1/discover/generate-idea",
            json={"video_id": video_id},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["brief"]["hook_analysis"]
