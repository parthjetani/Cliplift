"""Integration tests for niche management endpoints."""

import uuid

import pytest
from httpx import AsyncClient

from tests.test_creators import _create_real_user, authed_user  # noqa: F401


# ============================================================================
# Auth checks
# ============================================================================


class TestNichesAuth:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/niches")
        assert response.status_code == 401

    async def test_create_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/niches",
            json={"name": "test", "keywords": ["test"]},
        )
        assert response.status_code == 401

    async def test_delete_requires_auth(self, client: AsyncClient) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/niches/{fake_id}")
        assert response.status_code == 401


# ============================================================================
# Create
# ============================================================================


class TestCreateNiche:
    async def test_create_with_defaults(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/niches",
            json={
                "name": "Fitness Shorts",
                "keywords": ["fitness", "workout", "gym"],
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Fitness Shorts"
        assert body["keywords"] == ["fitness", "workout", "gym"]
        # Default platforms = all 4
        assert set(body["platforms"]) == {"youtube", "instagram", "linkedin", "tiktok"}
        assert body["is_active"] is True
        assert body["last_analyzed_at"] is None

    async def test_create_with_custom_platforms(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/niches",
            json={
                "name": "B2B SaaS",
                "keywords": ["b2b", "saas", "marketing"],
                "platforms": ["linkedin", "youtube"],
            },
            headers=headers,
        )
        assert response.status_code == 201
        assert set(response.json()["platforms"]) == {"linkedin", "youtube"}

    async def test_create_empty_keywords_rejected(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/niches",
            json={"name": "test", "keywords": []},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_create_too_many_keywords_rejected(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/niches",
            json={"name": "test", "keywords": [f"kw{i}" for i in range(25)]},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_create_invalid_platform_rejected(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/niches",
            json={"name": "test", "keywords": ["k"], "platforms": ["myspace"]},
            headers=headers,
        )
        assert response.status_code == 422


# ============================================================================
# List
# ============================================================================


class TestListNiches:
    async def test_empty_list_for_new_user(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.get("/api/v1/niches", headers=headers)
        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_create_then_list(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        await client.post(
            "/api/v1/niches",
            json={"name": "Niche 1", "keywords": ["a"]},
            headers=headers,
        )
        await client.post(
            "/api/v1/niches",
            json={"name": "Niche 2", "keywords": ["b"]},
            headers=headers,
        )
        list_resp = await client.get("/api/v1/niches", headers=headers)
        items = list_resp.json()["items"]
        assert len(items) == 2
        # Newest first
        names = [n["name"] for n in items]
        assert names == ["Niche 2", "Niche 1"]


# ============================================================================
# Update + delete
# ============================================================================


class TestUpdateDeleteNiche:
    async def test_update_name(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        create_resp = await client.post(
            "/api/v1/niches",
            json={"name": "Old Name", "keywords": ["k"]},
            headers=headers,
        )
        niche_id = create_resp.json()["id"]

        update_resp = await client.put(
            f"/api/v1/niches/{niche_id}",
            json={"name": "New Name"},
            headers=headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "New Name"
        # Other fields unchanged
        assert update_resp.json()["keywords"] == ["k"]

    async def test_update_partial(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        create_resp = await client.post(
            "/api/v1/niches",
            json={"name": "n", "keywords": ["a"], "is_active": True},
            headers=headers,
        )
        niche_id = create_resp.json()["id"]

        # Deactivate without touching other fields
        update_resp = await client.put(
            f"/api/v1/niches/{niche_id}",
            json={"is_active": False},
            headers=headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["is_active"] is False
        assert update_resp.json()["keywords"] == ["a"]

    async def test_delete_removes_from_list(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        create_resp = await client.post(
            "/api/v1/niches",
            json={"name": "to delete", "keywords": ["k"]},
            headers=headers,
        )
        niche_id = create_resp.json()["id"]

        delete_resp = await client.delete(
            f"/api/v1/niches/{niche_id}",
            headers=headers,
        )
        assert delete_resp.status_code == 204

        list_resp = await client.get("/api/v1/niches", headers=headers)
        assert list_resp.json()["items"] == []

    async def test_delete_unknown_returns_404(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/niches/{fake_id}", headers=headers)
        assert response.status_code == 404


# ============================================================================
# Feed
# ============================================================================


class TestNicheFeed:
    async def test_feed_empty_for_new_niche(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """A freshly-created niche has no feed items until the worker runs."""
        _, _, headers = authed_user
        create_resp = await client.post(
            "/api/v1/niches",
            json={"name": "fresh", "keywords": ["k"]},
            headers=headers,
        )
        niche_id = create_resp.json()["id"]

        feed_resp = await client.get(
            f"/api/v1/niches/{niche_id}/feed", headers=headers
        )
        assert feed_resp.status_code == 200
        assert feed_resp.json()["items"] == []

    async def test_feed_404_for_unknown_niche(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        fake_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v1/niches/{fake_id}/feed", headers=headers
        )
        assert response.status_code == 404


# ============================================================================
# Cross-team isolation
# ============================================================================


class TestNicheIsolation:
    async def test_user2_cannot_see_user1_niches(
        self, client: AsyncClient
    ) -> None:
        u1_id, _, u1_token = await _create_real_user()
        u2_id, _, u2_token = await _create_real_user()
        h1 = {"Authorization": f"Bearer {u1_token}"}
        h2 = {"Authorization": f"Bearer {u2_token}"}

        await client.post(
            "/api/v1/niches",
            json={"name": "user 1's niche", "keywords": ["secret"]},
            headers=h1,
        )

        # User 2 should see empty list
        u2_list = await client.get("/api/v1/niches", headers=h2)
        assert u2_list.json()["items"] == []

    async def test_user2_cannot_get_user1_niche(
        self, client: AsyncClient
    ) -> None:
        u1_id, _, u1_token = await _create_real_user()
        u2_id, _, u2_token = await _create_real_user()
        h1 = {"Authorization": f"Bearer {u1_token}"}
        h2 = {"Authorization": f"Bearer {u2_token}"}

        create_resp = await client.post(
            "/api/v1/niches",
            json={"name": "private", "keywords": ["k"]},
            headers=h1,
        )
        niche_id = create_resp.json()["id"]

        # User 2 trying to read user 1's niche → 404 (not 403, to avoid leaking existence)
        response = await client.get(f"/api/v1/niches/{niche_id}", headers=h2)
        assert response.status_code == 404
