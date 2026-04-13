"""OAuth provider factory — picks real or mock based on env config.

Pattern matches `app.platforms.factory`: missing API credentials → mock fallback.
This means the entire OAuth flow is testable end-to-end with no real Google/Meta
client_id needed.
"""

import logging

from app.config import Settings
from app.platforms.base import Platform
from app.publishing.oauth_providers.base import OAuthProvider
from app.publishing.oauth_providers.instagram import InstagramOAuthProvider
from app.publishing.oauth_providers.mock import MockOAuthProvider
from app.publishing.oauth_providers.youtube import YouTubeOAuthProvider

logger = logging.getLogger(__name__)


def get_oauth_provider(platform: Platform, settings: Settings) -> OAuthProvider:
    """Return the OAuth provider for a platform.

    Returns the real provider if its credentials are configured, else falls
    back to MockOAuthProvider for that platform.
    """
    if platform == Platform.YOUTUBE:
        if settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET:
            return YouTubeOAuthProvider(
                client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
                client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            )
        return MockOAuthProvider(Platform.YOUTUBE)

    if platform == Platform.INSTAGRAM:
        if settings.META_OAUTH_CLIENT_ID and settings.META_OAUTH_CLIENT_SECRET:
            return InstagramOAuthProvider(
                client_id=settings.META_OAUTH_CLIENT_ID,
                client_secret=settings.META_OAUTH_CLIENT_SECRET,
            )
        return MockOAuthProvider(Platform.INSTAGRAM)

    if platform == Platform.LINKEDIN:
        # LinkedIn Marketing API requires partner approval — Phase 3.
        # Mock-only for now.
        return MockOAuthProvider(Platform.LINKEDIN)

    if platform == Platform.TIKTOK:
        # TikTok Content Posting API requires app review — defer to Phase 2.
        return MockOAuthProvider(Platform.TIKTOK)

    raise ValueError(f"Unsupported platform for OAuth: {platform}")
