"""Real Stripe client — wraps the `stripe` Python SDK.

Activated when `STRIPE_SECRET_KEY` is set. All SDK calls are wrapped in
`asyncio.to_thread()` because the stripe SDK is synchronous and we're running
inside an async FastAPI handler.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import stripe

from app.billing.base import BillingEvent, CheckoutResult, PortalResult

logger = logging.getLogger(__name__)

# Mapping plan name → config env var name for price lookup
PLAN_PRICE_MAP = {
    "creator": "STRIPE_PRICE_CREATOR",
    "team": "STRIPE_PRICE_TEAM",
    "agency": "STRIPE_PRICE_AGENCY",
}


class RealStripeClient:
    """Production Stripe client backed by the `stripe` SDK."""

    def __init__(
        self,
        secret_key: str,
        webhook_secret: str,
        price_ids: dict[str, str],
    ) -> None:
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.price_ids = price_ids  # {"creator": "price_xxx", ...}
        stripe.api_key = secret_key

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
        price_id = self.price_ids.get(plan)
        if not price_id:
            raise ValueError(f"No Stripe price ID configured for plan '{plan}'")

        params: dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {"team_id": team_id, "plan": plan},
            "subscription_data": {
                "metadata": {"team_id": team_id, "plan": plan},
            },
        }

        if customer_id:
            params["customer"] = customer_id
        else:
            params["customer_email"] = customer_email

        session = await asyncio.to_thread(
            stripe.checkout.Session.create, **params
        )
        return CheckoutResult(
            session_id=session.id,
            checkout_url=session.url,
        )

    async def create_billing_portal_session(
        self,
        *,
        customer_id: str,
        return_url: str,
    ) -> PortalResult:
        session = await asyncio.to_thread(
            stripe.billing_portal.Session.create,
            customer=customer_id,
            return_url=return_url,
        )
        return PortalResult(portal_url=session.url)

    def verify_webhook_signature(
        self,
        payload: bytes,
        sig_header: str,
    ) -> dict[str, Any]:
        """Verify a Stripe webhook signature and return the parsed event."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return dict(event)
        except stripe.SignatureVerificationError as e:
            raise ValueError(f"Invalid Stripe signature: {e}") from e
        except ValueError as e:
            raise ValueError(f"Invalid webhook payload: {e}") from e

    def parse_billing_event(self, raw_event: dict[str, Any]) -> BillingEvent:
        """Normalize a real Stripe event into our internal shape.

        For checkout.session.completed, we read `metadata.plan` and
        `metadata.team_id` from the session object. For subscription events,
        we read from the subscription's metadata (set during checkout via
        `subscription_data.metadata`).
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
