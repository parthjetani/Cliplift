"""Publisher factory — builds a `PublisherRouter` for the current environment.

Mirror of `app.platforms.factory.build_router`. The publishing factory wires
each real publisher with its matching OAuth provider (so the publisher can
refresh access tokens at publish time without going back to settings).

Per-platform decisions:

- **YouTube** — real `YouTubeShortsPublisher` when Google OAuth credentials
  are configured (so it can mint real access tokens). When Google credentials
  are missing, the OAuth flow uses `MockOAuthProvider` which mints fake
  tokens — but those fake tokens cannot drive a real YouTube API call, so we
  also fall back to `MockPublisher` for YouTube. This keeps dev end-to-end
  mocked: the local environment never touches real Google APIs.
- **Instagram** — same gating logic against Meta credentials.
- **LinkedIn / TikTok** — always mock for now. LinkedIn publishing requires
  the Marketing API partnership (Phase 3); TikTok needs Content Posting API
  app review (Phase 2).
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.platforms.base import Platform
from app.publishing.oauth_factory import get_oauth_provider
from app.publishing.oauth_providers.mock import MockOAuthProvider
from app.publishing.publisher_router import PublisherRouter
from app.publishing.publishers.instagram import InstagramReelsPublisher
from app.publishing.publishers.mock import MockPublisher
from app.publishing.publishers.youtube import YouTubeShortsPublisher

logger = logging.getLogger(__name__)


def build_publisher_router(settings: Settings) -> PublisherRouter:
    """Construct the PublisherRouter for this environment.

    For each platform with a real publisher implementation, we check whether
    its OAuth provider is real or mocked. If the OAuth provider is mocked
    (i.e., the env vars are unset), we register `MockPublisher` for that
    platform too — calling a real API with mock tokens would just 401, and
    mocking end-to-end keeps the local dev story coherent.
    """
    router = PublisherRouter()

    # YouTube
    yt_oauth = get_oauth_provider(Platform.YOUTUBE, settings)
    if isinstance(yt_oauth, MockOAuthProvider):
        router.register(MockPublisher(Platform.YOUTUBE))
    else:
        router.register(YouTubeShortsPublisher(oauth_provider=yt_oauth))

    # Instagram (Meta app review approved 2026-04-11 — but still gated on
    # whether the META_OAUTH_CLIENT_ID env vars are actually set)
    ig_oauth = get_oauth_provider(Platform.INSTAGRAM, settings)
    if isinstance(ig_oauth, MockOAuthProvider):
        router.register(MockPublisher(Platform.INSTAGRAM))
    else:
        router.register(InstagramReelsPublisher(oauth_provider=ig_oauth))

    # LinkedIn — mock until Marketing API partnership lands (Phase 3).
    router.register(MockPublisher(Platform.LINKEDIN))

    # TikTok — mock until Content Posting API app review lands (Phase 2).
    router.register(MockPublisher(Platform.TIKTOK))

    logger.info(f"PublisherRouter built: {router.publisher_summary}")
    return router
