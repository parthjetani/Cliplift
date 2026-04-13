"""End-to-end OAuth flow tests using the mock provider.

These tests exercise the full authorize → callback → list → delete cycle
without needing real Google/Meta credentials. The mock provider's authorize_url
returns the callback URL directly with a fake code, so we can complete the
flow programmatically.
"""

import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient

from tests.test_creators import _create_real_user, authed_user  # noqa: F401


# ============================================================================
# Auth checks
# ============================================================================


class TestOAuthAuth:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/connections")
        assert response.status_code == 401

    async def test_authorize_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/connections/youtube/authorize")
        assert response.status_code == 401

    async def test_delete_requires_auth(self, client: AsyncClient) -> None:
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/connections/{fake_id}")
        assert response.status_code == 401


# ============================================================================
# Authorize endpoint
# ============================================================================


class TestAuthorize:
    async def test_authorize_returns_url_and_state(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/connections/youtube/authorize", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert "authorize_url" in body
        assert "state" in body
        assert body["platform"] == "youtube"
        assert len(body["state"]) >= 32  # URL-safe 32-byte token

    async def test_authorize_url_contains_state_and_code(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """Mock provider's authorize_url is the callback URL with code+state."""
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/connections/youtube/authorize", headers=headers
        )
        body = response.json()
        parsed = urlparse(body["authorize_url"])
        params = parse_qs(parsed.query)
        assert "code" in params
        assert "state" in params
        assert params["state"][0] == body["state"]
        assert params["code"][0].startswith("mock-code-")

    async def test_authorize_each_platform(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        for platform in ["youtube", "instagram", "linkedin", "tiktok"]:
            response = await client.post(
                f"/api/v1/connections/{platform}/authorize", headers=headers
            )
            assert response.status_code == 200, f"{platform} failed: {response.text}"
            assert response.json()["platform"] == platform


# ============================================================================
# Full callback flow
# ============================================================================


class TestCallbackFlow:
    async def test_full_oauth_flow_youtube(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """Authorize → follow callback → connection appears in list."""
        _, _, headers = authed_user

        # Step 1: authorize
        auth_resp = await client.post(
            "/api/v1/connections/youtube/authorize", headers=headers
        )
        assert auth_resp.status_code == 200
        body = auth_resp.json()
        callback_url = body["authorize_url"]

        # Extract path + query for our test client (drop the host)
        parsed = urlparse(callback_url)
        callback_path = parsed.path + "?" + parsed.query
        # Strip the API base URL prefix if present
        if callback_path.startswith("/api/v1/connections"):
            relative = callback_path
        else:
            relative = "/api/v1/connections/youtube/callback?" + parsed.query

        # Step 2: hit the callback (no auth header — state token authorizes)
        callback_resp = await client.get(relative, follow_redirects=False)
        assert callback_resp.status_code == 302
        # Should redirect to settings page
        assert "/dashboard/settings/connections" in callback_resp.headers.get("location", "")

        # Step 3: list connections — the new one should appear
        list_resp = await client.get("/api/v1/connections", headers=headers)
        assert list_resp.status_code == 200
        connections = list_resp.json()
        youtube_conns = [c for c in connections if c["platform"] == "youtube"]
        assert len(youtube_conns) == 1
        conn = youtube_conns[0]
        assert conn["platform_username"].startswith("youtube_user_")
        # Tokens should NEVER be in the response
        assert "access_token" not in conn
        assert "refresh_token" not in conn

    async def test_callback_invalid_state_rejected(
        self, client: AsyncClient
    ) -> None:
        """Callback with a state we never issued → 400."""
        response = await client.get(
            "/api/v1/connections/youtube/callback"
            "?code=mock-code-fake&state=never-issued-state"
        )
        assert response.status_code == 400

    async def test_callback_state_platform_mismatch(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """State issued for YouTube cannot complete an Instagram callback."""
        _, _, headers = authed_user
        auth_resp = await client.post(
            "/api/v1/connections/youtube/authorize", headers=headers
        )
        state = auth_resp.json()["state"]

        # Try to use the YouTube state on an Instagram callback
        response = await client.get(
            f"/api/v1/connections/instagram/callback?code=mock-code-x&state={state}"
        )
        assert response.status_code == 400


# ============================================================================
# List + delete
# ============================================================================


class TestListDeleteConnection:
    async def test_empty_list_for_new_user(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.get("/api/v1/connections", headers=headers)
        assert response.status_code == 200
        assert response.json() == []

    async def test_delete_removes_connection(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user

        # Complete a connection via the mock flow
        auth_resp = await client.post(
            "/api/v1/connections/instagram/authorize", headers=headers
        )
        callback_url = auth_resp.json()["authorize_url"]
        parsed = urlparse(callback_url)
        await client.get(parsed.path + "?" + parsed.query, follow_redirects=False)

        list_resp = await client.get("/api/v1/connections", headers=headers)
        connections = list_resp.json()
        assert len(connections) >= 1
        conn_id = connections[0]["id"]

        # Delete
        delete_resp = await client.delete(
            f"/api/v1/connections/{conn_id}", headers=headers
        )
        assert delete_resp.status_code == 204

        # Verify gone
        list_after = await client.get("/api/v1/connections", headers=headers)
        ids_after = [c["id"] for c in list_after.json()]
        assert conn_id not in ids_after

    async def test_delete_unknown_returns_404(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/api/v1/connections/{fake_id}", headers=headers)
        assert response.status_code == 404


# ============================================================================
# Cross-team isolation
# ============================================================================


class TestConnectionIsolation:
    async def test_user2_cannot_see_user1_connections(
        self, client: AsyncClient
    ) -> None:
        u1_id, _, u1_token = await _create_real_user()
        u2_id, _, u2_token = await _create_real_user()
        h1 = {"Authorization": f"Bearer {u1_token}"}
        h2 = {"Authorization": f"Bearer {u2_token}"}

        # User 1 connects YouTube
        auth = await client.post(
            "/api/v1/connections/youtube/authorize", headers=h1
        )
        callback_url = auth.json()["authorize_url"]
        parsed = urlparse(callback_url)
        await client.get(parsed.path + "?" + parsed.query, follow_redirects=False)

        # User 2 should see no connections
        u2_list = await client.get("/api/v1/connections", headers=h2)
        assert u2_list.json() == []
