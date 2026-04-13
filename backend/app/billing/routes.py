"""Billing routes — checkout, customer portal, webhook.

- POST /billing/checkout — auth required, returns Stripe checkout URL
- POST /billing/portal — auth required, returns Stripe billing portal URL
- POST /billing/webhook — NO auth (Stripe signs the request)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_profile, get_current_team
from app.auth.models import Profile, Team
from app.billing.base import StripeClient
from app.billing.schemas import (
    BillingPortalResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
)
from app.billing.service import (
    create_billing_portal_session,
    create_checkout_session,
    handle_webhook_event,
)
from app.database import get_db

router = APIRouter(prefix="/billing", tags=["billing"])


def get_stripe_client(request: Request) -> StripeClient:
    """Pull the StripeClient off app.state (set in main.py lifespan)."""
    return request.app.state.stripe_client


# ----------------------------------------------------------------------------
# Checkout
# ----------------------------------------------------------------------------


@router.post(
    "/checkout",
    response_model=CheckoutSessionResponse,
    summary="Create a Stripe Checkout Session",
)
async def checkout_endpoint(
    payload: CheckoutSessionRequest,
    team: Annotated[Team, Depends(get_current_team)],
    profile: Annotated[Profile, Depends(get_current_profile)],
    stripe_client: Annotated[StripeClient, Depends(get_stripe_client)],
) -> CheckoutSessionResponse:
    return await create_checkout_session(
        stripe_client, team, profile.email, payload
    )


# ----------------------------------------------------------------------------
# Customer Portal
# ----------------------------------------------------------------------------


@router.post(
    "/portal",
    response_model=BillingPortalResponse,
    summary="Create a Stripe Billing Portal link",
)
async def portal_endpoint(
    team: Annotated[Team, Depends(get_current_team)],
    stripe_client: Annotated[StripeClient, Depends(get_stripe_client)],
) -> BillingPortalResponse:
    return await create_billing_portal_session(stripe_client, team)


# ----------------------------------------------------------------------------
# Webhook
# ----------------------------------------------------------------------------


@router.post(
    "/webhook",
    summary="Stripe webhook receiver (no auth — Stripe signs)",
)
async def webhook_endpoint(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    stripe_client: Annotated[StripeClient, Depends(get_stripe_client)],
    stripe_signature: Annotated[str, Header(alias="Stripe-Signature")] = "",
) -> dict:
    payload = await request.body()
    return await handle_webhook_event(db, stripe_client, payload, stripe_signature)
