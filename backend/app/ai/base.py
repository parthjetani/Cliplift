"""Abstract AIClient interface."""

from abc import ABC, abstractmethod

from app.ai.schemas import ContentBrief
from app.platforms.base import VideoSearchResult


class AIClient(ABC):
    """Abstract base for AI content brief generation."""

    name: str

    @abstractmethod
    async def generate_content_brief(
        self, video: VideoSearchResult
    ) -> ContentBrief:
        """Generate a structured content brief from a video's metadata.

        The brief should be actionable: hook analysis, format, suggested
        caption, hashtags, and CTA. Tone should be terse and direct (matching
        Claude Haiku's output style).
        """
