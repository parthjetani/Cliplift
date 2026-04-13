"""Billing service — checkout, portal, webhook handling.

Routes call into here; this module owns the Stripe interactions and the
DB mutations triggered by webhook events.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Team
from app.billing.base import BillingEvent, StripeClient
from app.billing.plans import VALID_PLANS
from app.billing.schemas import CheckoutSessionRequest, CheckoutSessionResponse, BillingPortalResponse
from app.config import settings

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Checkout
# ----------------------------------------------------------------------------


async def create_checkout_session(
    stripe_client: StripeClient,
    team: Team,
    owner_email: str,
    payload: CheckoutSessionRequest,
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout Session for the team to upgrade/subscribe."""
    result = await stripe_client.create_checkout_session(
        customer_id=team.stripe_customer_id,
        customer_email=owner_email,
        team_id=str(team.id),
        plan=payload.plan,
        billing_period=payload.billing_period,
        success_url=f"{settings.FRONTEND_URL}/dashboard/settings/billing?checkout=success",
        cancel_url=f"{settings.FRONTEND_URL}/dashboard/settings/billing?checkout=cancelled",
    )
    return CheckoutSessionResponse(
        checkout_url=result.checkout_url,
        session_id=result.session_id,
    )


# ----------------------------------------------------------------------------
# Customer Portal
# ----------------------------------------------------------------------------


async def create_billing_portal_session(
    stripe_client: StripeClient,
    team: Team,
) -> BillingPortalResponse:
    """Create a Stripe Billing Portal link for subscription management."""
    if not team.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found — complete a checkout first",
        )
    result = await stripe_client.create_billing_portal_session(
        customer_id=team.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/dashboard/settings/billing",
    )
    return BillingPortalResponse(portal_url=result.portal_url)


# ----------------------------------------------------------------------------
# Webhook
# ----------------------------------------------------------------------------


async def handle_webhook_event(
    db: AsyncSession,
    stripe_client: StripeClient,
    payload: bytes,
    sig_header: str,
) -> dict:
    """Verify + dispatch a Stripe webhook event.

    Returns a summary dict (for logging / response body). Never raises on
    known event types — unknown types are logged and ignored (Stripe sends
    many events we don't care about).
    """
    try:
        raw_event = stripe_client.verify_webhook_signature(payload, sig_header)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Webhook signature verification failed: {e}",
        )

    event = stripe_client.parse_billing_event(raw_event)
    logger.info(
        f"Billing webhook: {event.event_type} team={event.team_id} "
        f"plan={event.plan} sub={event.subscription_id}"
    )

    if event.event_type == "checkout.session.completed":
        await _handle_checkout_completed(db, event)
        return {"handled": True, "event": event.event_type}

    if event.event_type == "customer.subscription.updated":
        await _handle_subscription_updated(db, event)
        return {"handled": True, "event": event.event_type}

    if event.event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(db, event)
        return {"handled": True, "event": event.event_type}

    logger.debug(f"Ignoring unhandled event type: {event.event_type}")
    return {"handled": False, "event": event.event_type}


async def _resolve_team(db: AsyncSession, event: BillingEvent) -> Team | None:
    """Find the team referenced by a webhook event."""
    if not event.team_id:
        logger.warning(f"Webhook event {event.event_type} has no team_id in metadata")
        return None
    try:
        team_uuid = uuid.UUID(event.team_id)
    except ValueError:
        logger.warning(f"Invalid team_id in webhook metadata: {event.team_id}")
        return None
    result = await db.execute(select(Team).where(Team.id == team_uuid))
    return result.scalar_one_or_none()


async def _handle_checkout_completed(db: AsyncSession, event: BillingEvent) -> None:
    """User completed Stripe checkout → flip plan, set customer + subscription IDs, clear trial."""
    team = await _resolve_team(db, event)
    if not team:
        logger.error(f"checkout.session.completed: team {event.team_id} not found")
        return

    new_plan = event.plan
    if new_plan and new_plan in VALID_PLANS and new_plan != "cancelled":
        team.plan = new_plan
    if event.customer_id:
        team.stripe_customer_id = event.customer_id
    if event.subscription_id:
        team.stripe_subscription_id = event.subscription_id
    team.trial_ends_at = None  # trial is over — they're paying now

    await db.commit()
    logger.info(
        f"Team {team.id} upgraded to {team.plan} via checkout "
        f"(customer={team.stripe_customer_id}, sub={team.stripe_subscription_id})"
    )


async def _handle_subscription_updated(db: AsyncSession, event: BillingEvent) -> None:
    """Subscription plan changed (upgrade/downgrade via portal). Does NOT touch trial_ends_at."""
    team = await _resolve_team(db, event)
    if not team:
        logger.error(f"subscription.updated: team {event.team_id} not found")
        return

    new_plan = event.plan
    if new_plan and new_plan in VALID_PLANS and new_plan != "cancelled":
        team.plan = new_plan
    if event.subscription_id:
        team.stripe_subscription_id = event.subscription_id

    await db.commit()
    logger.info(f"Team {team.id} plan updated to {team.plan}")


async def _handle_subscription_deleted(db: AsyncSession, event: BillingEvent) -> None:
    """Subscription cancelled — HARD CUTOFF. Blocks all writes, reads stay open."""
    team = await _resolve_team(db, event)
    if not team:
        logger.error(f"subscription.deleted: team {event.team_id} not found")
        return

    team.plan = "cancelled"
    team.trial_ends_at = None  # no automatic trial on cancellation
    # Keep stripe_customer_id and stripe_subscription_id for record-keeping
    # (and so reactivation checkout can reference the same customer)

    await db.commit()
    logger.info(f"Team {team.id} subscription cancelled — plan set to 'cancelled'")
