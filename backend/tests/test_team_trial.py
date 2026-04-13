"""Tests for team trial_ends_at + TeamResponse computed fields."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.auth.schemas import TeamResponse
from tests.test_creators import _create_real_user, authed_user  # noqa: F401


# ============================================================================
# TeamResponse computed fields (unit tests, no DB)
# ============================================================================


class TestTeamResponseTrialFlags:
    def test_active_trial_no_payment(self) -> None:
        """Fresh signup: trial in the future, no subscription → is_trial_active=True."""
        resp = TeamResponse(
            id=uuid.uuid4(),
            name="Test",
            owner_id=uuid.uuid4(),
            plan="creator",
            stripe_customer_id=None,
            stripe_subscription_id=None,
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=5),
            created_at=datetime.now(timezone.utc),
        )
        assert resp.is_trial_active is True
        assert resp.is_trial_expired is False

    def test_expired_trial_never_paid(self) -> None:
        """Trial past, no subscription → is_trial_expired=True."""
        resp = TeamResponse(
            id=uuid.uuid4(),
            name="Test",
            owner_id=uuid.uuid4(),
            plan="creator",
            stripe_customer_id=None,
            stripe_subscription_id=None,
            trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1),
            created_at=datetime.now(timezone.utc),
        )
        assert resp.is_trial_active is False
        assert resp.is_trial_expired is True

    def test_expired_trial_but_paid(self) -> None:
        """Trial past, but subscription exists → NOT expired (billing is active)."""
        resp = TeamResponse(
            id=uuid.uuid4(),
            name="Test",
            owner_id=uuid.uuid4(),
            plan="team",
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_456",
            trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1),
            created_at=datetime.now(timezone.utc),
        )
        assert resp.is_trial_active is False
        assert resp.is_trial_expired is False

    def test_no_trial_ends_at(self) -> None:
        """After checkout completes, trial_ends_at is cleared → both flags False."""
        resp = TeamResponse(
            id=uuid.uuid4(),
            name="Test",
            owner_id=uuid.uuid4(),
            plan="team",
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_456",
            trial_ends_at=None,
            created_at=datetime.now(timezone.utc),
        )
        assert resp.is_trial_active is False
        assert resp.is_trial_expired is False


# ============================================================================
# GET /teams/me integration tests
# ============================================================================


class TestGetTeamEndpoint:
    async def test_requires_auth(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/teams/me")
        assert response.status_code == 401

    async def test_returns_team_with_trial(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """New user's team should have plan=creator and an active trial."""
        _, _, headers = authed_user
        response = await client.get("/api/v1/teams/me", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["plan"] == "creator"
        assert body["trial_ends_at"] is not None
        assert body["is_trial_active"] is True
        assert body["is_trial_expired"] is False
        assert body["stripe_customer_id"] is None
        assert body["stripe_subscription_id"] is None
