"""Tests for MockStripeClient — deterministic, no external calls."""

from __future__ import annotations

import json

import pytest

from app.billing.base import BillingEvent, CheckoutResult, PortalResult
from app.billing.factory import build_stripe_client
from app.billing.mock import MockStripeClient
from app.config import Settings


class TestMockCheckoutSession:
    async def test_returns_checkout_result_shape(self) -> None:
        client = MockStripeClient()
        result = await client.create_checkout_session(
            customer_id=None,
            customer_email="test@cliplift.com",
            team_id="team-123",
            plan="team",
            billing_period="monthly",
            success_url="http://localhost:3000/success",
            cancel_url="http://localhost:3000/cancel",
        )
        assert isinstance(result, CheckoutResult)
        assert result.session_id.startswith("mock_cs_")
        assert result.checkout_url.startswith("https://mock.local/checkout/")

    async def test_deterministic_for_same_inputs(self) -> None:
        client = MockStripeClient()
        kwargs = dict(
            customer_id=None,
            customer_email="test@cliplift.com",
            team_id="team-abc",
            plan="agency",
            billing_period="annual",
            success_url="http://localhost:3000/s",
            cancel_url="http://localhost:3000/c",
        )
        r1 = await client.create_checkout_session(**kwargs)
        r2 = await client.create_checkout_session(**kwargs)
        assert r1.session_id == r2.session_id
        assert r1.checkout_url == r2.checkout_url


class TestMockBillingPortal:
    async def test_returns_portal_url(self) -> None:
        client = MockStripeClient()
        result = await client.create_billing_portal_session(
            customer_id="cus_test",
            return_url="http://localhost:3000/settings/billing",
        )
        assert isinstance(result, PortalResult)
        assert "cus_test" in result.portal_url


class TestMockWebhookSignature:
    def test_accepts_mock_signature(self) -> None:
        client = MockStripeClient()
        event = MockStripeClient.build_synthetic_event(
            "checkout.session.completed", team_id="t1", plan="team"
        )
        parsed = client.verify_webhook_signature(
            json.dumps(event).encode(), "mock-signature"
        )
        assert parsed["type"] == "checkout.session.completed"

    def test_rejects_bad_signature(self) -> None:
        client = MockStripeClient()
        with pytest.raises(ValueError, match="Invalid mock signature"):
            client.verify_webhook_signature(b"{}", "wrong-sig")


class TestMockParseEvent:
    def test_checkout_completed_event(self) -> None:
        client = MockStripeClient()
        raw = MockStripeClient.build_synthetic_event(
            "checkout.session.completed",
            team_id="team-xyz",
            plan="agency",
            subscription_id="sub_456",
            customer_id="cus_789",
        )
        event = client.parse_billing_event(raw)
        assert isinstance(event, BillingEvent)
        assert event.event_type == "checkout.session.completed"
        assert event.team_id == "team-xyz"
        assert event.plan == "agency"
        assert event.subscription_id == "sub_456"
        assert event.customer_id == "cus_789"

    def test_subscription_deleted_event(self) -> None:
        client = MockStripeClient()
        raw = MockStripeClient.build_synthetic_event(
            "customer.subscription.deleted",
            team_id="team-del",
            plan="team",
        )
        event = client.parse_billing_event(raw)
        assert event.event_type == "customer.subscription.deleted"
        assert event.team_id == "team-del"


class TestBuildStripeClientFactory:
    def test_returns_mock_when_no_key(self) -> None:
        s = Settings(STRIPE_SECRET_KEY="")
        client = build_stripe_client(s)
        assert isinstance(client, MockStripeClient)

    def test_returns_real_when_key_set(self) -> None:
        """With STRIPE_SECRET_KEY set, factory returns RealStripeClient."""
        from app.billing.real import RealStripeClient

        s = Settings(STRIPE_SECRET_KEY="sk_test_fake")
        client = build_stripe_client(s)
        assert isinstance(client, RealStripeClient)
