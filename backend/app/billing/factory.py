"""Stripe client factory — picks real or mock based on env config.

Same pattern as `common/storage.py:build_storage` and `ai/factory.py`.
"""

import logging

from app.billing.base import StripeClient
from app.billing.mock import MockStripeClient
from app.config import Settings

logger = logging.getLogger(__name__)


def build_stripe_client(settings: Settings) -> StripeClient:
    """Return a StripeClient implementation based on environment config.

    - `STRIPE_SECRET_KEY` set → `RealStripeClient`
    - Otherwise              → `MockStripeClient`
    """
    if settings.STRIPE_SECRET_KEY:
        from app.billing.real import RealStripeClient

        logger.info("Stripe: LIVE (real Stripe SDK)")
        return RealStripeClient(
            secret_key=settings.STRIPE_SECRET_KEY,
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
            price_ids={
                "creator": settings.STRIPE_PRICE_CREATOR,
                "team": settings.STRIPE_PRICE_TEAM,
                "agency": settings.STRIPE_PRICE_AGENCY,
            },
        )

    logger.info("Stripe: MOCK (deterministic, no API calls)")
    return MockStripeClient()
