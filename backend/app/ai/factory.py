"""AI client factory — picks real or mock based on env config."""

import logging

from app.ai.base import AIClient
from app.ai.claude import ClaudeAIClient
from app.ai.mock import MockAIClient
from app.config import Settings

logger = logging.getLogger(__name__)


def get_ai_client(settings: Settings) -> AIClient:
    """Return the AI client for this environment.

    Real ClaudeAIClient when ANTHROPIC_API_KEY is set, MockAIClient otherwise.
    """
    if settings.ANTHROPIC_API_KEY:
        logger.info("AI client: Claude (claude-haiku-4-5)")
        return ClaudeAIClient(api_key=settings.ANTHROPIC_API_KEY)
    else:
        logger.info("AI client: Mock (deterministic, no API calls)")
        return MockAIClient()
