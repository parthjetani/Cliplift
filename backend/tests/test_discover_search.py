"""Integration tests for the /api/v1/discover/search endpoint."""

from httpx import AsyncClient


class TestDiscoverSearchEndpoint:
    async def test_search_no_auth_required(self, client: AsyncClient) -> None:
        """Search is PUBLIC — no auth header needed."""
        response = await client.post(
            "/api/v1/discover/search",
            json={"query": "fitness", "platforms": ["youtube"], "limit_per_platform": 5},
        )
        assert response.status_code == 200

    async def test_search_returns_video_results(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/discover/search",
            json={"query": "fitness", "platforms": ["youtube"], "limit_per_platform": 10},
        )
        body = response.json()
        assert body["query"] == "fitness"
        assert body["total"] == 10
        assert len(body["videos"]) == 10
        assert body["videos"][0]["platform"] == "youtube"

    async def test_search_includes_outlier_scores(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/discover/search",
            json={"query": "fitness", "platforms": ["youtube"], "limit_per_platform": 20},
        )
        body = response.json()
        # At least one outlier should be detected (mock injects 2)
        assert body["outlier_count"] >= 1
        # Outliers should be sorted to the top
        assert body["videos"][0]["is_outlier"] is True

    async def test_search_multi_platform(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/discover/search",
            json={
                "query": "fitness",
                "platforms": ["youtube", "linkedin", "tiktok", "instagram"],
                "limit_per_platform": 5,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 20  # 5 per platform × 4 platforms
        assert len(body["by_platform"]) == 4
        platforms_in_response = {s["platform"] for s in body["by_platform"]}
        assert platforms_in_response == {"youtube", "linkedin", "tiktok", "instagram"}

    async def test_search_validation_empty_query(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/discover/search",
            json={"query": "", "platforms": ["youtube"]},
        )
        assert response.status_code == 422

    async def test_search_validation_invalid_platform(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/discover/search",
            json={"query": "fitness", "platforms": ["myspace"]},
        )
        assert response.status_code == 422

    async def test_search_validation_limit_too_high(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/discover/search",
            json={"query": "fitness", "platforms": ["youtube"], "limit_per_platform": 100},
        )
        assert response.status_code == 422

    async def test_search_deterministic(self, client: AsyncClient) -> None:
        """Same query returns same results (mock determinism)."""
        body_a = {"query": "fitness", "platforms": ["youtube"], "limit_per_platform": 5}
        r1 = await client.post("/api/v1/discover/search", json=body_a)
        r2 = await client.post("/api/v1/discover/search", json=body_a)
        ids1 = [v["platform_video_id"] for v in r1.json()["videos"]]
        ids2 = [v["platform_video_id"] for v in r2.json()["videos"]]
        assert ids1 == ids2

    async def test_providers_endpoint(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/discover/providers")
        assert response.status_code == 200
        body = response.json()
        assert "youtube" in body
        assert "linkedin" in body
        assert "tiktok" in body
        assert "instagram" in body
        # Without API keys set, all should be mocks
        assert all(v == "mock" for v in body.values())
