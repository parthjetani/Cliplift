"""Real Claude AI client using the Anthropic SDK.

Uses claude-haiku-4-5 for cost efficiency. Structured JSON output via
system prompt + tool_use pattern.
"""

import json
import logging
from datetime import datetime, timezone

import anthropic

from app.ai.base import AIClient
from app.ai.schemas import ContentBrief
from app.platforms.base import VideoSearchResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a short-form video content strategist. Given a viral video's metadata, generate a structured content brief that helps a creator produce a response video.

Be terse and direct. Each field should be 1-2 sentences max. No fluff.

Return valid JSON matching this exact schema:
{
  "hook_analysis": "Why the original hook works (1-2 sentences)",
  "format": "Video format description, e.g. 'talking head + b-roll cuts, 20s'",
  "suggested_hook": "Your version of the hook (1 sentence)",
  "suggested_caption": "Full caption ready to post (2-3 sentences max)",
  "suggested_hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "cta": "Call to action (1 sentence)"
}"""


class ClaudeAIClient(AIClient):
    """Real Anthropic client — calls claude-haiku-4-5."""

    name = "claude"

    def __init__(self, api_key: str) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def generate_content_brief(
        self, video: VideoSearchResult
    ) -> ContentBrief:
        user_message = (
            f"Platform: {video.platform.value}\n"
            f"Title: {video.title}\n"
            f"Views: {video.views:,}\n"
            f"Likes: {video.likes:,}\n"
            f"Comments: {video.comments:,}\n"
            f"Engagement rate: {video.engagement_rate or 0:.2%}\n"
            f"Hashtags: {', '.join(video.hashtags[:10]) if video.hashtags else 'none'}\n"
            f"Description: {(video.description or '')[:200]}\n"
        )

        try:
            response = await self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            # Extract JSON from the response
            text = response.content[0].text.strip()
            # Handle potential markdown code blocks
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)

            return ContentBrief(
                hook_analysis=data["hook_analysis"],
                format=data["format"],
                suggested_hook=data["suggested_hook"],
                suggested_caption=data["suggested_caption"],
                suggested_hashtags=data.get("suggested_hashtags", []),
                cta=data["cta"],
                generated_at=datetime.now(timezone.utc),
                cached=False,
            )

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Failed to parse Claude response: {e}")
            raise ValueError(f"Claude returned invalid JSON: {e}") from e
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise ValueError(f"Claude API error: {e}") from e
