"""Factory that builds a DataProviderRouter based on environment configuration.

Decides per platform whether to use the real provider (if its API key is set)
or fall back to MockDataProvider. Called once at app startup from `main.py`.
"""

import logging

from app.config import Settings
from app.platforms.base import Platform
from app.platforms.data365 import Data365Provider
from app.platforms.mock import MockDataProvider
from app.platforms.netrows import NetrowsProvider
from app.platforms.router import DataProviderRouter
from app.platforms.youtube import YouTubeProvider

logger = logging.getLogger(__name__)


def build_router(settings: Settings) -> DataProviderRouter:
    """Construct the DataProviderRouter for this environment.

    Per-platform logic: if the relevant API key is set, register the real
    provider; otherwise register a MockDataProvider for that platform.
    """
    router = DataProviderRouter()

    # YouTube — official API (free, 10K quota/day)
    if settings.YOUTUBE_API_KEY:
        router.register(YouTubeProvider(api_key=settings.YOUTUBE_API_KEY))
    else:
        router.register(MockDataProvider(Platform.YOUTUBE))

    # LinkedIn — Netrows API (€49/mo, our differentiator)
    if settings.NETROWS_API_KEY:
        router.register(NetrowsProvider(api_key=settings.NETROWS_API_KEY))
    else:
        router.register(MockDataProvider(Platform.LINKEDIN))

    # TikTok + Instagram — both via Data365 ($99/mo)
    if settings.DATA365_API_KEY:
        router.register(Data365Provider(api_key=settings.DATA365_API_KEY, platform=Platform.TIKTOK))
        router.register(
            Data365Provider(api_key=settings.DATA365_API_KEY, platform=Platform.INSTAGRAM)
        )
    else:
        router.register(MockDataProvider(Platform.TIKTOK))
        router.register(MockDataProvider(Platform.INSTAGRAM))

    logger.info(f"DataProviderRouter built: {router.provider_summary}")
    return router
