"""Tests for POST /api/v1/publishing/uploads/presign."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.test_creators import _upgrade_team_plan, authed_user  # noqa: F401


# ============================================================================
# Auth
# ============================================================================


class TestPresignAuth:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/publishing/uploads/presign",
            json={"filename": "test.mp4", "content_type": "video/mp4"},
        )
        assert response.status_code == 401


# ============================================================================
# Successful presign
# ============================================================================


class TestPresignSuccess:
    async def test_returns_url_key_and_expiry(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        await _upgrade_team_plan(client, headers, "team")  # Creator tier blocks scheduling
        response = await client.post(
            "/api/v1/publishing/uploads/presign",
            json={"filename": "myvid.mp4", "content_type": "video/mp4"},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert "upload_url" in body
        assert "file_key" in body
        assert "expires_at" in body
        assert body["upload_url"].startswith("http")

    async def test_file_key_namespaced_by_team(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        await _upgrade_team_plan(client, headers, "team")
        response = await client.post(
            "/api/v1/publishing/uploads/presign",
            json={"filename": "v.mp4", "content_type": "video/mp4"},
            headers=headers,
        )
        body = response.json()
        # file_key shape: <team_uuid>/<random_uuid>/<filename>
        parts = body["file_key"].split("/")
        assert len(parts) == 3
        assert parts[2] == "v.mp4"
        # First part should look like a UUID
        assert len(parts[0]) == 36

    async def test_accepts_quicktime_and_webm(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        await _upgrade_team_plan(client, headers, "team")
        for ct in ("video/mp4", "video/quicktime", "video/webm"):
            response = await client.post(
                "/api/v1/publishing/uploads/presign",
                json={"filename": "v.mp4", "content_type": ct},
                headers=headers,
            )
            assert response.status_code == 200, f"{ct} failed: {response.text}"


# ============================================================================
# Validation
# ============================================================================


class TestPresignValidation:
    async def test_invalid_content_type_rejected(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/publishing/uploads/presign",
            json={"filename": "test.gif", "content_type": "image/gif"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_path_traversal_filename_rejected(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/publishing/uploads/presign",
            json={"filename": "../etc/passwd", "content_type": "video/mp4"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_dotfile_rejected(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/publishing/uploads/presign",
            json={"filename": ".hidden", "content_type": "video/mp4"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_empty_filename_rejected(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.post(
            "/api/v1/publishing/uploads/presign",
            json={"filename": "", "content_type": "video/mp4"},
            headers=headers,
        )
        assert response.status_code == 422
