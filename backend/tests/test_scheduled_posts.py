"""Tests for /api/v1/publishing/scheduled-posts CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import pytest
from httpx import AsyncClient

from tests.test_creators import _create_real_user, _upgrade_team_plan, authed_user  # noqa: F401


# ============================================================================
# Helpers
# ============================================================================


async def _connect_youtube(client: AsyncClient, headers: dict) -> str:
    """Run the mock OAuth flow and return the new connection_id.

    Upgrades the team to 'team' plan first — Creator tier blocks scheduling
    and limits to 1 platform connection, both of which would break these tests.
    """
    await _upgrade_team_plan(client, headers, "team")
    auth_resp = await client.post(
        "/api/v1/connections/youtube/authorize", headers=headers
    )
    assert auth_resp.status_code == 200
    callback_url = auth_resp.json()["authorize_url"]
    parsed = urlparse(callback_url)
    callback_path = parsed.path + "?" + parsed.query
    cb_resp = await client.get(callback_path, follow_redirects=False)
    assert cb_resp.status_code == 302

    list_resp = await client.get("/api/v1/connections", headers=headers)
    youtube_conns = [
        c for c in list_resp.json() if c["platform"] == "youtube"
    ]
    assert len(youtube_conns) >= 1
    return youtube_conns[-1]["id"]


def _post_payload(
    connection_id: str,
    *,
    scheduled_for: datetime | None = None,
    title: str = "Test post",
    file_key: str = "team/x/test.mp4",
) -> dict:
    if scheduled_for is None:
        scheduled_for = datetime.now(timezone.utc) + timedelta(hours=1)
    return {
        "connection_id": connection_id,
        "platform": "youtube",
        "file_key": file_key,
        "title": title,
        "description": "A test post",
        "hashtags": ["test", "cliplift"],
        "scheduled_for": scheduled_for.isoformat(),
    }


# ============================================================================
# Auth
# ============================================================================


class TestScheduledPostsAuth:
    async def test_create_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json={"connection_id": str(uuid.uuid4()), "platform": "youtube"},
        )
        assert response.status_code == 401

    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/publishing/scheduled-posts")
        assert response.status_code == 401

    async def test_get_requires_auth(self, client: AsyncClient) -> None:
        response = await client.get(
            f"/api/v1/publishing/scheduled-posts/{uuid.uuid4()}"
        )
        assert response.status_code == 401

    async def test_delete_requires_auth(self, client: AsyncClient) -> None:
        response = await client.delete(
            f"/api/v1/publishing/scheduled-posts/{uuid.uuid4()}"
        )
        assert response.status_code == 401


# ============================================================================
# Create
# ============================================================================


class TestCreateScheduledPost:
    async def test_create_with_valid_connection(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        conn_id = await _connect_youtube(client, headers)

        response = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(conn_id),
            headers=headers,
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["platform"] == "youtube"
        assert body["title"] == "Test post"
        assert body["status"] == "scheduled"  # future scheduled_for
        assert body["connection_id"] == conn_id
        assert body["created_by"] is not None

    async def test_past_scheduled_for_starts_as_draft(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        conn_id = await _connect_youtube(client, headers)
        past = datetime.now(timezone.utc) - timedelta(hours=1)

        response = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(conn_id, scheduled_for=past),
            headers=headers,
        )
        assert response.status_code == 201
        assert response.json()["status"] == "draft"

    async def test_create_with_unknown_connection_404(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        await _upgrade_team_plan(client, headers, "team")  # enforcement gates fire before 404 otherwise
        response = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(str(uuid.uuid4())),
            headers=headers,
        )
        assert response.status_code == 404

    async def test_platform_mismatch_rejected(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        conn_id = await _connect_youtube(client, headers)
        payload = _post_payload(conn_id)
        payload["platform"] = "instagram"  # mismatch with youtube connection

        response = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 400


# ============================================================================
# List + Get
# ============================================================================


class TestListAndGetScheduledPosts:
    async def test_empty_list_for_new_user(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.get(
            "/api/v1/publishing/scheduled-posts", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["has_more"] is False

    async def test_list_after_create(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        conn_id = await _connect_youtube(client, headers)
        await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(conn_id),
            headers=headers,
        )

        response = await client.get(
            "/api/v1/publishing/scheduled-posts", headers=headers
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) >= 1
        assert body["items"][0]["platform"] == "youtube"

    async def test_status_filter(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        conn_id = await _connect_youtube(client, headers)

        # One scheduled (future), one draft (past)
        await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(conn_id),
            headers=headers,
        )
        await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(
                conn_id,
                scheduled_for=datetime.now(timezone.utc) - timedelta(hours=1),
            ),
            headers=headers,
        )

        sched = await client.get(
            "/api/v1/publishing/scheduled-posts?status=scheduled", headers=headers
        )
        draft = await client.get(
            "/api/v1/publishing/scheduled-posts?status=draft", headers=headers
        )
        assert all(p["status"] == "scheduled" for p in sched.json()["items"])
        assert all(p["status"] == "draft" for p in draft.json()["items"])

    async def test_get_unknown_post_404(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        response = await client.get(
            f"/api/v1/publishing/scheduled-posts/{uuid.uuid4()}", headers=headers
        )
        assert response.status_code == 404


# ============================================================================
# Update
# ============================================================================


class TestUpdateScheduledPost:
    async def test_update_title(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        conn_id = await _connect_youtube(client, headers)
        create = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(conn_id),
            headers=headers,
        )
        post_id = create.json()["id"]

        response = await client.patch(
            f"/api/v1/publishing/scheduled-posts/{post_id}",
            json={"title": "Updated title"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated title"

    async def test_status_transition_scheduled_to_draft(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        conn_id = await _connect_youtube(client, headers)
        create = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(conn_id),
            headers=headers,
        )
        post_id = create.json()["id"]
        assert create.json()["status"] == "scheduled"

        response = await client.patch(
            f"/api/v1/publishing/scheduled-posts/{post_id}",
            json={"status": "draft"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "draft"

    async def test_invalid_status_transition_rejected(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        conn_id = await _connect_youtube(client, headers)
        create = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(conn_id),
            headers=headers,
        )
        post_id = create.json()["id"]

        # scheduled → published is not allowed via the API (worker only)
        response = await client.patch(
            f"/api/v1/publishing/scheduled-posts/{post_id}",
            json={"status": "published"},
            headers=headers,
        )
        assert response.status_code == 409


# ============================================================================
# Delete
# ============================================================================


class TestDeleteScheduledPost:
    async def test_delete_removes_post(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        conn_id = await _connect_youtube(client, headers)
        create = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(conn_id),
            headers=headers,
        )
        post_id = create.json()["id"]

        delete_resp = await client.delete(
            f"/api/v1/publishing/scheduled-posts/{post_id}", headers=headers
        )
        assert delete_resp.status_code == 204

        get_resp = await client.get(
            f"/api/v1/publishing/scheduled-posts/{post_id}", headers=headers
        )
        assert get_resp.status_code == 404


# ============================================================================
# Cross-team isolation
# ============================================================================


class TestCrossTeamIsolation:
    async def test_user_cannot_read_other_teams_post(
        self, client: AsyncClient
    ) -> None:
        _, _, t1 = await _create_real_user()
        _, _, t2 = await _create_real_user()
        h1 = {"Authorization": f"Bearer {t1}"}
        h2 = {"Authorization": f"Bearer {t2}"}

        conn_id = await _connect_youtube(client, h1)
        create = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(conn_id),
            headers=h1,
        )
        post_id = create.json()["id"]

        # User 2 cannot see it
        get_resp = await client.get(
            f"/api/v1/publishing/scheduled-posts/{post_id}", headers=h2
        )
        assert get_resp.status_code == 404

    async def test_user_cannot_use_other_teams_connection(
        self, client: AsyncClient
    ) -> None:
        _, _, t1 = await _create_real_user()
        _, _, t2 = await _create_real_user()
        h1 = {"Authorization": f"Bearer {t1}"}
        h2 = {"Authorization": f"Bearer {t2}"}

        # User 1 connects YouTube (also upgrades to team plan)
        conn_id = await _connect_youtube(client, h1)

        # User 2 also needs team plan to bypass scheduling enforcement
        await _upgrade_team_plan(client, h2, "team")

        # User 2 tries to create a post using user 1's connection
        response = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(conn_id),
            headers=h2,
        )
        assert response.status_code == 404

    async def test_user_cannot_delete_other_teams_post(
        self, client: AsyncClient
    ) -> None:
        _, _, t1 = await _create_real_user()
        _, _, t2 = await _create_real_user()
        h1 = {"Authorization": f"Bearer {t1}"}
        h2 = {"Authorization": f"Bearer {t2}"}

        conn_id = await _connect_youtube(client, h1)
        create = await client.post(
            "/api/v1/publishing/scheduled-posts",
            json=_post_payload(conn_id),
            headers=h1,
        )
        post_id = create.json()["id"]

        delete_resp = await client.delete(
            f"/api/v1/publishing/scheduled-posts/{post_id}", headers=h2
        )
        assert delete_resp.status_code == 404
