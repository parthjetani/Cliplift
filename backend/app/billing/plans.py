"""Plan-tier limits — single source of truth.

Values copied from `tmp/STRATEGY.md` pricing table. This is a code dict, not
a DB table — pricing tiers change rarely and changes need a code review anyway.

The enforcement middleware in `billing/enforcement.py` reads from this dict
via `PLAN_LIMITS[team.plan]`. The legacy per-row columns on the `teams` table
(`max_tracked_creators`, `max_seats`) are NOT the source of truth — they remain
for backwards compat and will be cleaned up in a later migration.
"""

from pydantic import BaseModel


class PlanLimits(BaseModel):
    """Limits for a single pricing tier."""

    tracked_creators: int
    max_users: int
    max_platforms: int  # 1 for creator (the strongest upgrade hook), 4 for team/agency
    scheduling: bool  # Creator tier cannot schedule posts
    api_access: bool  # Agency only — placeholder for Phase 2 API tokens
    monthly_price_usd: int
    annual_price_usd: int  # 30% discount on annual


PLAN_LIMITS: dict[str, PlanLimits] = {
    "creator": PlanLimits(
        tracked_creators=3,
        max_users=1,
        max_platforms=1,
        scheduling=False,
        api_access=False,
        monthly_price_usd=29,
        annual_price_usd=244,  # $29 × 12 × 0.7 ≈ $244
    ),
    "team": PlanLimits(
        tracked_creators=25,
        max_users=5,
        max_platforms=4,
        scheduling=True,
        api_access=False,
        monthly_price_usd=79,
        annual_price_usd=664,  # $79 × 12 × 0.7 ≈ $664
    ),
    "agency": PlanLimits(
        tracked_creators=50,
        max_users=25,
        max_platforms=4,
        scheduling=True,
        api_access=True,
        monthly_price_usd=149,
        annual_price_usd=1252,  # $149 × 12 × 0.7 ≈ $1252
    ),
}

# Valid plan values (includes "cancelled" which has no limits entry — the
# enforcement middleware hard-blocks all writes for cancelled teams before
# looking up PLAN_LIMITS)
VALID_PLANS = {"creator", "team", "agency", "cancelled"}

# Ordered from cheapest to most expensive — used for "suggested_plan" in
# upgrade prompts (next tier up from current)
PLAN_ORDER = ["creator", "team", "agency"]


def next_plan_up(current_plan: str) -> str | None:
    """Return the next tier above `current_plan`, or None if already at the top."""
    try:
        idx = PLAN_ORDER.index(current_plan)
        return PLAN_ORDER[idx + 1] if idx + 1 < len(PLAN_ORDER) else None
    except ValueError:
        return PLAN_ORDER[0]  # cancelled / unknown → suggest creator
