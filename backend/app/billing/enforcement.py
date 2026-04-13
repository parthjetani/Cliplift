"""Plan enforcement gates — blocks writes for cancelled/expired teams and
per-tier limit checks.

Usage pattern in routes:

    # Write endpoint — use require_active_plan INSTEAD of get_current_team
    @router.post("/track")
    async def track(
        team: Annotated[Team, Depends(require_active_plan)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ):
        await enforce_creator_tracking_limit(db, team)
        ...

    # Read endpoint — keep using get_current_team as before
    @router.get("")
    async def list_items(
        team: Annotated[Team, Depends(get_current_team)],
        ...
    ):
        ...
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_team
from app.auth.models import Team
from app.billing.plans import PLAN_LIMITS, next_plan_up
from app.creators.models import CreatorTracking
from app.database import get_db
from app.publishing.models import PlatformConnection

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# PlanLimitExceeded — 402 Payment Required
# ----------------------------------------------------------------------------


class PlanLimitExceeded(HTTPException):
    """402 Payment Required with structured upgrade prompt."""

    def __init__(
        self,
        detail: str,
        limit_name: str,
        current_plan: str,
        suggested_plan: str | None = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail,
        )
        self.limit_name = limit_name
        self.current_plan = current_plan
        self.suggested_plan = suggested_plan or next_plan_up(current_plan)


# ----------------------------------------------------------------------------
# require_active_plan — the master gate for all write endpoints
# ----------------------------------------------------------------------------


async def require_active_plan(
    team: Annotated[Team, Depends(get_current_team)],
) -> Team:
    """FastAPI dependency that blocks writes for cancelled or trial-expired teams.

    Returns the team if active; raises PlanLimitExceeded(402) otherwise. Use
    this INSTEAD of `get_current_team` on every POST/PUT/PATCH/DELETE endpoint.
    Read-only (GET) endpoints keep using `get_current_team` directly.

    Two failure modes checked in order:
    1. team.plan == "cancelled" (subscription was cancelled via Stripe webhook)
    2. trial_ends_at < now() AND stripe_subscription_id IS NULL (trial expired,
       never paid — no Stripe event would ever fire to flip them to cancelled,
       so we compute this gate from existing columns on every write request)
    """
    if team.plan == "cancelled":
        raise PlanLimitExceeded(
            detail=(
                "Your subscription has been cancelled. "
                "Reactivate to continue creating content."
            ),
            limit_name="subscription_cancelled",
            current_plan="cancelled",
            suggested_plan="creator",
        )

    if (
        team.trial_ends_at is not None
        and team.trial_ends_at <= datetime.now(timezone.utc)
        and not team.stripe_subscription_id
    ):
        raise PlanLimitExceeded(
            detail=(
                "Your 7-day trial has ended. "
                "Pick a plan to continue tracking and publishing."
            ),
            limit_name="trial_expired",
            current_plan=team.plan,
            suggested_plan="creator",
        )

    return team


# ----------------------------------------------------------------------------
# Per-limit gates — called explicitly in route handlers
# ----------------------------------------------------------------------------


async def enforce_creator_tracking_limit(
    db: AsyncSession, team: Team
) -> None:
    """Raise 402 if the team is at or over its tracked-creator cap."""
    limits = PLAN_LIMITS.get(team.plan)
    if not limits:
        return  # unknown plan (shouldn't happen) — let it through

    result = await db.execute(
        select(func.count())
        .select_from(CreatorTracking)
        .where(CreatorTracking.team_id == team.id)
    )
    current = result.scalar() or 0

    if current >= limits.tracked_creators:
        suggested = next_plan_up(team.plan)
        suggested_limit = (
            PLAN_LIMITS[suggested].tracked_creators if suggested else "unlimited"
        )
        raise PlanLimitExceeded(
            detail=(
                f"{team.plan.title()} plan allows {limits.tracked_creators} "
                f"tracked creators. "
                f"Upgrade to {suggested.title() if suggested else 'a higher plan'} "
                f"for {suggested_limit}."
            ),
            limit_name="tracked_creators",
            current_plan=team.plan,
            suggested_plan=suggested,
        )


async def enforce_platform_connection_limit(
    db: AsyncSession, team: Team
) -> None:
    """Raise 402 if the team is at or over its max_platforms cap.

    Creator tier = 1 platform total (the strongest upgrade hook).
    Team/Agency = 4 (all platforms).
    """
    limits = PLAN_LIMITS.get(team.plan)
    if not limits:
        return

    result = await db.execute(
        select(func.count(func.distinct(PlatformConnection.platform)))
        .where(PlatformConnection.team_id == team.id)
    )
    current = result.scalar() or 0

    if current >= limits.max_platforms:
        suggested = next_plan_up(team.plan)
        raise PlanLimitExceeded(
            detail=(
                f"{team.plan.title()} plan allows {limits.max_platforms} "
                f"platform connection{'s' if limits.max_platforms > 1 else ''}. "
                f"Upgrade to {suggested.title() if suggested else 'a higher plan'} "
                f"to connect more platforms."
            ),
            limit_name="max_platforms",
            current_plan=team.plan,
            suggested_plan=suggested,
        )


def enforce_scheduling_enabled(team: Team) -> None:
    """Raise 402 if the team's plan doesn't include scheduling.

    Creator tier has scheduling=False. Team/Agency have it enabled.
    """
    limits = PLAN_LIMITS.get(team.plan)
    if not limits:
        return

    if not limits.scheduling:
        raise PlanLimitExceeded(
            detail=(
                f"{team.plan.title()} plan doesn't include post scheduling. "
                f"Upgrade to Team to schedule and publish content."
            ),
            limit_name="scheduling",
            current_plan=team.plan,
            suggested_plan="team",
        )
