"""Abstract StripeClient protocol — same mock-first pattern as StorageBackend.

Concrete implementations:
- `MockStripeClient` (billing/mock.py) — deterministic, no external calls
- `RealStripeClient` (billing/real.py, Chunk 23) — wraps the `stripe` SDK
"""

from __future__ import annotations

from typing import Any, Protocol


class CheckoutResult:
    """Normalized return from create_checkout_session."""

    __slots__ = ("session_id", "checkout_url")

    def __init__(self, session_id: str, checkout_url: str) -> None:
        self.session_id = session_id
        self.checkout_url = checkout_url


class PortalResult:
    """Normalized return from create_billing_portal_session."""

    __slots__ = ("portal_url",)

    def __init__(self, portal_url: str) -> None:
        self.portal_url = portal_url


class BillingEvent:
    """Normalized webhook event — agnostic to Stripe types."""

    __slots__ = ("event_type", "team_id", "plan", "subscription_id", "customer_id")

    def __init__(
        self,
        event_type: str,
        team_id: str | None = None,
        plan: str | None = None,
        subscription_id: str | None = None,
        customer_id: str | None = None,
    ) -> None:
        self.event_type = event_type
        self.team_id = team_id
        self.plan = plan
        self.subscription_id = subscription_id
        self.customer_id = customer_id


class StripeClient(Protocol):
    """Protocol every Stripe client backend implements."""

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
    ) -> CheckoutResult: ...

    async def create_billing_portal_session(
        self,
        *,
        customer_id: str,
        return_url: str,
    ) -> PortalResult: ...

    def verify_webhook_signature(
        self,
        payload: bytes,
        sig_header: str,
    ) -> dict[str, Any]:
        """Verify + parse a webhook payload. Returns the raw event dict.

        Raises ValueError on invalid or missing signature.
        """
        ...

    def parse_billing_event(self, raw_event: dict[str, Any]) -> BillingEvent:
        """Normalize a raw Stripe event into our internal shape."""
        ...
