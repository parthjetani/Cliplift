"""Mock Stripe client — deterministic, no external calls.

Used when `STRIPE_SECRET_KEY` is empty (dev + tests). Returns stable checkout
session IDs seeded by team_id + plan so tests can assert exact values.

The `fire_synthetic_event` method lets tests simulate webhook events by
constructing a `BillingEvent` directly — no HTTP involved.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.billing.base import BillingEvent, CheckoutResult, PortalResult, StripeClient


class MockStripeClient:
    """No-op Stripe client with deterministic output."""

    def _seed(self, *parts: str) -> str:
        raw = ":".join(parts)
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    async def create_checkout_session(
        self,
        *,
        customer_id: str | None,
        customer_email: str,
        team_id: str,
        plan: str,
        billing_period: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutResult:
        session_id = f"mock_cs_{self._seed(team_id, plan, billing_period)}"
        return CheckoutResult(
            session_id=session_id,
            checkout_url=f"https://mock.local/checkout/{session_id}",
        )

    async def create_billing_portal_session(
        self,
        *,
        customer_id: str,
        return_url: str,
    ) -> PortalResult:
        return PortalResult(
            portal_url=f"https://mock.local/portal/{customer_id}",
        )

    def verify_webhook_signature(
        self,
        payload: bytes,
        sig_header: str,
    ) -> dict[str, Any]:
        """Mock accepts any payload with a `mock-signature` header value."""
        if sig_header != "mock-signature":
            raise ValueError("Invalid mock signature")
        import json

        return json.loads(payload)

    def parse_billing_event(self, raw_event: dict[str, Any]) -> BillingEvent:
        """Parse a mock event dict into a BillingEvent.

        Mock events use the same shape as real Stripe events but with
        simplified metadata.
        """
        event_type = raw_event.get("type", "")
        data_obj = raw_event.get("data", {}).get("object", {})
        metadata = data_obj.get("metadata", {})
        return BillingEvent(
            event_type=event_type,
            team_id=metadata.get("team_id"),
            plan=metadata.get("plan"),
            subscription_id=data_obj.get("subscription") or data_obj.get("id"),
            customer_id=data_obj.get("customer"),
        )

    @staticmethod
    def build_synthetic_event(
        event_type: str,
        team_id: str,
        plan: str = "creator",
        subscription_id: str = "mock_sub_123",
        customer_id: str = "mock_cus_123",
    ) -> dict[str, Any]:
        """Build a synthetic webhook event dict for testing.

        Call `verify_webhook_signature(json.dumps(event), "mock-signature")`
        then `parse_billing_event(result)` to get a `BillingEvent`.
        """
        return {
            "type": event_type,
            "data": {
                "object": {
                    "id": subscription_id,
                    "customer": customer_id,
                    "subscription": subscription_id,
                    "metadata": {
                        "team_id": team_id,
                        "plan": plan,
                    },
                },
            },
        }
