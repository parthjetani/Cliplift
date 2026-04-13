"""Tests for the PLAN_LIMITS config and plan helpers."""

from app.billing.plans import PLAN_LIMITS, PLAN_ORDER, VALID_PLANS, next_plan_up


class TestPlanLimitsConfig:
    def test_all_tiers_have_required_fields(self) -> None:
        for name, limits in PLAN_LIMITS.items():
            assert limits.tracked_creators > 0, f"{name}: tracked_creators must be positive"
            assert limits.max_users > 0, f"{name}: max_users must be positive"
            assert limits.max_platforms > 0, f"{name}: max_platforms must be positive"
            assert limits.monthly_price_usd > 0, f"{name}: price must be positive"
            assert limits.annual_price_usd > 0, f"{name}: annual price must be positive"
            assert isinstance(limits.scheduling, bool)
            assert isinstance(limits.api_access, bool)

    def test_limits_monotonically_increase(self) -> None:
        """Higher tiers should have >= limits on every numeric field."""
        creator = PLAN_LIMITS["creator"]
        team = PLAN_LIMITS["team"]
        agency = PLAN_LIMITS["agency"]

        assert creator.tracked_creators <= team.tracked_creators <= agency.tracked_creators
        assert creator.max_users <= team.max_users <= agency.max_users
        assert creator.max_platforms <= team.max_platforms <= agency.max_platforms
        assert creator.monthly_price_usd <= team.monthly_price_usd <= agency.monthly_price_usd

    def test_creator_tier_restrictions(self) -> None:
        c = PLAN_LIMITS["creator"]
        assert c.tracked_creators == 3
        assert c.max_users == 1
        assert c.max_platforms == 1
        assert c.scheduling is False
        assert c.api_access is False

    def test_team_tier_scheduling_enabled(self) -> None:
        assert PLAN_LIMITS["team"].scheduling is True
        assert PLAN_LIMITS["agency"].scheduling is True

    def test_agency_has_api_access(self) -> None:
        assert PLAN_LIMITS["agency"].api_access is True
        assert PLAN_LIMITS["team"].api_access is False

    def test_annual_pricing_is_30_percent_discount(self) -> None:
        for name, limits in PLAN_LIMITS.items():
            annual_full = limits.monthly_price_usd * 12
            discounted = round(annual_full * 0.7)
            assert abs(limits.annual_price_usd - discounted) <= 1, (
                f"{name}: annual ${limits.annual_price_usd} should be ~30% off "
                f"${annual_full} (expected ~${discounted})"
            )

    def test_valid_plans_includes_cancelled(self) -> None:
        assert "cancelled" in VALID_PLANS
        for plan in PLAN_ORDER:
            assert plan in VALID_PLANS


class TestNextPlanUp:
    def test_creator_suggests_team(self) -> None:
        assert next_plan_up("creator") == "team"

    def test_team_suggests_agency(self) -> None:
        assert next_plan_up("team") == "agency"

    def test_agency_is_top(self) -> None:
        assert next_plan_up("agency") is None

    def test_cancelled_suggests_creator(self) -> None:
        assert next_plan_up("cancelled") == "creator"
