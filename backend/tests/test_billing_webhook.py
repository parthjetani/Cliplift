"""Tests for the billing webhook handler — event dispatch + DB mutations."""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient

from app.billing.mock import MockStripeClient
from app.config import settings
from tests.test_creators import _create_real_user, authed_user  # noqa: F401


def _webhook_headers(sig: str = "mock-signature") -> dict:
    return {"Stripe-Signature": sig, "Content-Type": "application/json"}


def _unique_ids() -> tuple[str, str]:
    """Generate unique sub/cus IDs so tests don't collide on the UNIQUE constraint
    when sharing a persistent DB across runs."""
    u = uuid.uuid4().hex[:8]
    return f"sub_{u}", f"cus_{u}"


class TestWebhookSignature:
    async def test_invalid_signature_returns_401(
        self, client: AsyncClient
    ) -> None:
        event = MockStripeClient.build_synthetic_event(
            "checkout.session.completed", team_id=str(uuid.uuid4())
        )
        response = await client.post(
            "/api/v1/billing/webhook",
            content=json.dumps(event),
            headers=_webhook_headers("bad-sig"),
        )
        assert response.status_code == 401

    async def test_valid_mock_signature_accepted(
        self, client: AsyncClient
    ) -> None:
        event = MockStripeClient.build_synthetic_event(
            "some.unknown.event", team_id=str(uuid.uuid4())
        )
        response = await client.post(
            "/api/v1/billing/webhook",
            content=json.dumps(event),
            headers=_webhook_headers(),
        )
        assert response.status_code == 200
        assert response.json()["handled"] is False  # unknown event type


class TestCheckoutCompleted:
    async def test_flips_plan_and_clears_trial(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """checkout.session.completed → team.plan flips, trial_ends_at cleared."""
        _, _, headers = authed_user
        sub_id, cus_id = _unique_ids()

        # Get the team_id
        team_resp = await client.get("/api/v1/teams/me", headers=headers)
        team_id = team_resp.json()["id"]
        assert team_resp.json()["plan"] == "creator"
        assert team_resp.json()["trial_ends_at"] is not None

        # Fire the webhook
        event = MockStripeClient.build_synthetic_event(
            "checkout.session.completed",
            team_id=team_id,
            plan="team",
            subscription_id=sub_id,
            customer_id=cus_id,
        )
        wh_resp = await client.post(
            "/api/v1/billing/webhook",
            content=json.dumps(event),
            headers=_webhook_headers(),
        )
        assert wh_resp.status_code == 200
        assert wh_resp.json()["handled"] is True

        # Verify the team was updated
        team_after = await client.get("/api/v1/teams/me", headers=headers)
        body = team_after.json()
        assert body["plan"] == "team"
        assert body["trial_ends_at"] is None
        assert body["stripe_customer_id"] == cus_id
        assert body["stripe_subscription_id"] == sub_id
        assert body["is_trial_active"] is False
        assert body["is_trial_expired"] is False


class TestSubscriptionUpdated:
    async def test_updates_plan_without_touching_trial(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        _, _, headers = authed_user
        sub_id, cus_id = _unique_ids()
        team_id = (await client.get("/api/v1/teams/me", headers=headers)).json()["id"]

        # First complete checkout to get a paying team
        checkout_event = MockStripeClient.build_synthetic_event(
            "checkout.session.completed",
            team_id=team_id,
            plan="team",
            subscription_id=sub_id,
            customer_id=cus_id,
        )
        await client.post(
            "/api/v1/billing/webhook",
            content=json.dumps(checkout_event),
            headers=_webhook_headers(),
        )

        # Now simulate a plan change via the portal (subscription.updated)
        update_event = MockStripeClient.build_synthetic_event(
            "customer.subscription.updated",
            team_id=team_id,
            plan="agency",
            subscription_id=sub_id,
            customer_id=cus_id,
        )
        resp = await client.post(
            "/api/v1/billing/webhook",
            content=json.dumps(update_event),
            headers=_webhook_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["handled"] is True

        team = (await client.get("/api/v1/teams/me", headers=headers)).json()
        assert team["plan"] == "agency"
        assert team["trial_ends_at"] is None


class TestSubscriptionDeleted:
    async def test_hard_cancellation(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """subscription.deleted → team.plan = 'cancelled', trial_ends_at = None."""
        _, _, headers = authed_user
        sub_id, cus_id = _unique_ids()
        team_id = (await client.get("/api/v1/teams/me", headers=headers)).json()["id"]

        # Complete checkout first
        checkout_event = MockStripeClient.build_synthetic_event(
            "checkout.session.completed",
            team_id=team_id,
            plan="team",
            subscription_id=sub_id,
            customer_id=cus_id,
        )
        await client.post(
            "/api/v1/billing/webhook",
            content=json.dumps(checkout_event),
            headers=_webhook_headers(),
        )

        # Cancel the subscription
        delete_event = MockStripeClient.build_synthetic_event(
            "customer.subscription.deleted",
            team_id=team_id,
            plan="team",
            subscription_id=sub_id,
            customer_id=cus_id,
        )
        resp = await client.post(
            "/api/v1/billing/webhook",
            content=json.dumps(delete_event),
            headers=_webhook_headers(),
        )
        assert resp.status_code == 200

        team = (await client.get("/api/v1/teams/me", headers=headers)).json()
        assert team["plan"] == "cancelled"
        assert team["trial_ends_at"] is None
        assert team["stripe_customer_id"] == cus_id
        assert team["stripe_subscription_id"] == sub_id

    async def test_reactivation_after_cancellation(
        self, client: AsyncClient, authed_user: tuple[str, str, dict]
    ) -> None:
        """Cancelled team completes fresh checkout → back to paid plan."""
        _, _, headers = authed_user
        sub_id, cus_id = _unique_ids()
        team_id = (await client.get("/api/v1/teams/me", headers=headers)).json()["id"]

        # Checkout → cancel → re-checkout
        for event_type, plan in [
            ("checkout.session.completed", "creator"),
            ("customer.subscription.deleted", "creator"),
            ("checkout.session.completed", "agency"),
        ]:
            event = MockStripeClient.build_synthetic_event(
                event_type,
                team_id=team_id,
                plan=plan,
                subscription_id=sub_id,
                customer_id=cus_id,
            )
            await client.post(
                "/api/v1/billing/webhook",
                content=json.dumps(event),
                headers=_webhook_headers(),
            )

        team = (await client.get("/api/v1/teams/me", headers=headers)).json()
        assert team["plan"] == "agency"
        assert team["trial_ends_at"] is None
