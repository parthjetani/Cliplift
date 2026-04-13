"""Mock AI client — deterministic briefs matching Haiku's terse tone.

Output quality intentionally matches what claude-haiku-4-5 would return:
short sentences, bullet-point-length analysis, no floral prose. This way
beta testers won't be disappointed when the real model activates.
"""

import hashlib
from datetime import datetime, timezone

from app.ai.base import AIClient
from app.ai.schemas import ContentBrief
from app.platforms.base import VideoSearchResult


# Pools of short, Haiku-tone fragments — seeded by video title hash
_HOOK_ANALYSES = [
    "Opens with a pattern interrupt — unexpected visual grabs attention in the first 0.5s.",
    "Uses a direct question as the hook. Works because it triggers curiosity gap.",
    "Starts with a bold claim that contradicts conventional wisdom. Retention driver.",
    "The hook leverages social proof ('everyone is doing X'). Creates FOMO.",
    "Text overlay with a number anchors attention. Specific > vague for hooks.",
    "POV format creates immediate relatability. Viewer self-selects in under 1 second.",
]

_FORMATS = [
    "Talking head with jump cuts. 15-30s. Text overlays for key points.",
    "B-roll montage with voiceover. 20-40s. No face needed.",
    "Split-screen before/after. 10-20s. High contrast visual.",
    "Screen recording with face cam overlay. 30-60s. Tutorial style.",
    "Trending audio + text overlay. 10-15s. Minimal production.",
    "Story time with captions. 30-45s. Conversational delivery.",
]

_CTAS = [
    "Follow for more breakdowns like this.",
    "Save this for later — you'll need it.",
    "Drop a comment if you've seen this trend too.",
    "Share with someone who needs to hear this.",
    "Hit follow if you want the next part.",
    "Link in bio for the full breakdown.",
]


def _seed(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16)


class MockAIClient(AIClient):
    """Returns deterministic, Haiku-terse briefs. No API calls."""

    name = "mock"

    async def generate_content_brief(
        self, video: VideoSearchResult
    ) -> ContentBrief:
        seed = _seed(video.title or video.platform_video_id)

        hook = _HOOK_ANALYSES[seed % len(_HOOK_ANALYSES)]
        fmt = _FORMATS[seed % len(_FORMATS)]
        cta = _CTAS[seed % len(_CTAS)]

        # Build a suggested hook from the original title
        title_words = (video.title or "this trend").split()
        hook_prefix = " ".join(title_words[:4]) if len(title_words) > 4 else video.title or "This"
        suggested_hook = f"What if I told you {hook_prefix.lower()} is wrong?"

        # Caption — short, punchy, Haiku-length
        caption = (
            f"Most people get this wrong about {(video.title or 'this').lower()[:40]}. "
            f"Here's what actually works."
        )

        # Hashtags from the video + generic ones
        base_tags = video.hashtags[:3] if video.hashtags else ["shorts", "viral"]
        extra_tags = ["trending", "tips", video.platform.value, "cliplift"]
        all_tags = list(dict.fromkeys(base_tags + extra_tags))[:8]

        return ContentBrief(
            hook_analysis=hook,
            format=fmt,
            suggested_hook=suggested_hook,
            suggested_caption=caption,
            suggested_hashtags=all_tags,
            cta=cta,
            generated_at=datetime.now(timezone.utc),
            cached=False,
        )
