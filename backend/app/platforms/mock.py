"""Mock data provider — deterministic fake data for development and tests.

Activated automatically when a real provider's API key is missing. The full
stack works end-to-end with no external services.

Determinism: same (query, platform) → same results, every time. Important for
tests and for users to see consistent results when they re-run a search.
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone

from app.platforms.base import (
    CreatorProfile,
    DataProvider,
    Platform,
    VideoMetrics,
    VideoSearchResult,
)

# Realistic-ish creator name pool — first + last from common name lists
_FIRST_NAMES = [
    "Alex", "Jamie", "Riley", "Morgan", "Casey", "Taylor", "Jordan", "Avery",
    "Quinn", "Drew", "Sam", "Reese", "Cameron", "Skyler", "Hayden", "Rowan",
    "Parker", "Emerson", "Finley", "Sage", "River", "Phoenix", "Indigo", "Wren",
]
_LAST_NAMES = [
    "Chen", "Patel", "Nguyen", "Garcia", "Johnson", "Kim", "Silva", "Müller",
    "Rossi", "Singh", "Lopez", "Wright", "Brooks", "Hayes", "Reyes", "Bennett",
    "Cruz", "Foster", "Rivera", "Morgan", "Bell", "Cooper", "Ward", "Gray",
]

_TITLE_TEMPLATES = [
    "{query} — what nobody tells you",
    "I tried {query} for 30 days — here's what happened",
    "The {query} trend is back and it's bigger than ever",
    "Why every creator is talking about {query}",
    "{query} hack that broke the internet",
    "Stop doing {query} like this. Do this instead.",
    "POV: you discover {query} for the first time",
    "{query} — explained in 60 seconds",
    "I was wrong about {query}. Here's why.",
    "The {query} framework that 10x'd my reach",
    "Nobody is talking about this {query} mistake",
    "{query} 101 — everything you need to know",
]

_HASHTAG_POOL = [
    "viral", "trending", "fyp", "shorts", "reels", "tiktok", "creator",
    "growth", "marketing", "tutorial", "tips", "howto", "behindthescenes",
]


def _seed_for(query: str, platform: Platform) -> int:
    """Stable hash → seed mapping. Same input → same output."""
    h = hashlib.md5(f"{platform.value}:{query.lower()}".encode()).hexdigest()
    return int(h[:16], 16)


def _slugify(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")[:32]


class MockDataProvider(DataProvider):
    """Returns deterministic fake data for any platform.

    Used as a fallback when real provider API keys are missing. Generated data
    includes 2-3 obvious outliers per result set so outlier detection can be
    visually verified during development.
    """

    name = "mock"

    def __init__(self, platform: Platform) -> None:
        self.platform = platform

    async def search_videos(
        self,
        query: str,
        limit: int = 20,
    ) -> list[VideoSearchResult]:
        rng = random.Random(_seed_for(query, self.platform))
        results: list[VideoSearchResult] = []

        for i in range(limit):
            # Log-normal distribution gives a realistic long tail of view counts
            base_views = int(rng.lognormvariate(mu=10.5, sigma=1.4))

            # Inject 2 obvious outliers in the top of the result set
            if i < 2:
                views = base_views * rng.randint(12, 25)
            else:
                views = base_views

            # Engagement rate varies by platform — LinkedIn is lower, TikTok higher
            base_er = {
                Platform.YOUTUBE: 0.04,
                Platform.INSTAGRAM: 0.06,
                Platform.LINKEDIN: 0.025,
                Platform.TIKTOK: 0.09,
            }[self.platform]
            engagement_rate = base_er * rng.uniform(0.6, 1.6)

            likes = int(views * engagement_rate * rng.uniform(0.75, 0.92))
            comments = int(views * engagement_rate * rng.uniform(0.05, 0.15))
            shares = int(views * engagement_rate * rng.uniform(0.02, 0.10))

            first = rng.choice(_FIRST_NAMES)
            last = rng.choice(_LAST_NAMES)
            display_name = f"{first} {last}"
            username = f"{first.lower()}{last.lower()}{rng.randint(1, 999)}"
            creator_pid = f"mock-creator-{rng.randint(100000, 999999)}"

            video_pid = f"mock-{self.platform.value}-{rng.randint(10**9, 10**10 - 1)}"
            title = rng.choice(_TITLE_TEMPLATES).format(query=query.title())
            published = datetime.now(timezone.utc) - timedelta(
                days=rng.randint(1, 120),
                hours=rng.randint(0, 23),
            )

            # Random subset of 3 hashtags + the query as a hashtag
            tags = rng.sample(_HASHTAG_POOL, k=3)
            hashtags = [_slugify(query)] + tags

            results.append(
                VideoSearchResult(
                    platform=self.platform,
                    platform_video_id=video_pid,
                    url=f"https://{self.platform.value}.example.com/v/{video_pid}",
                    title=title,
                    description=f"A mock {self.platform.value} video about {query}.",
                    creator_username=username,
                    creator_display_name=display_name,
                    creator_platform_id=creator_pid,
                    creator_followers=rng.randint(1_000, 5_000_000),
                    views=views,
                    likes=likes,
                    comments=comments,
                    shares=shares,
                    engagement_rate=round(engagement_rate, 4),
                    published_at=published,
                    thumbnail_url=f"https://picsum.photos/seed/{video_pid}/640/360",
                    duration_seconds=rng.randint(15, 60),
                    hashtags=hashtags,
                )
            )

        return results

    async def get_creator(self, platform_id: str) -> CreatorProfile | None:
        rng = random.Random(_seed_for(platform_id, self.platform))
        first = rng.choice(_FIRST_NAMES)
        last = rng.choice(_LAST_NAMES)

        return CreatorProfile(
            platform=self.platform,
            platform_id=platform_id,
            username=f"{first.lower()}{last.lower()}",
            display_name=f"{first} {last}",
            avatar_url=f"https://picsum.photos/seed/{platform_id}/200/200",
            bio=f"Mock creator on {self.platform.value}. Posts about creator economy.",
            followers=rng.randint(1_000, 5_000_000),
            following=rng.randint(50, 2_000),
            total_videos=rng.randint(20, 800),
            verified=rng.random() > 0.7,
        )

    async def get_video_metrics(self, platform_video_id: str) -> VideoMetrics | None:
        rng = random.Random(_seed_for(platform_video_id, self.platform))
        views = int(rng.lognormvariate(11, 1.5))
        engagement_rate = rng.uniform(0.02, 0.10)
        return VideoMetrics(
            platform_video_id=platform_video_id,
            views=views,
            likes=int(views * engagement_rate * 0.85),
            comments=int(views * engagement_rate * 0.10),
            shares=int(views * engagement_rate * 0.05),
            engagement_rate=round(engagement_rate, 4),
            fetched_at=datetime.now(timezone.utc),
        )
