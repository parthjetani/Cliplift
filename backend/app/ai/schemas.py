"""Pydantic schemas for AI content briefs."""

from datetime import datetime

from pydantic import BaseModel, Field


class ContentBrief(BaseModel):
    """Structured content brief generated from an outlier video.

    Each field is a short, actionable paragraph — not an essay. Matches the
    tone of Claude Haiku: terse, direct, useful.
    """

    hook_analysis: str = Field(description="Why the original hook works (1-2 sentences)")
    format: str = Field(description="Video format description, e.g. 'talking head + b-roll cuts'")
    suggested_hook: str = Field(description="Your version of the hook (1 sentence)")
    suggested_caption: str = Field(description="Full caption ready to post (2-3 sentences)")
    suggested_hashtags: list[str] = Field(description="5-8 relevant hashtags")
    cta: str = Field(description="Call to action for the viewer (1 sentence)")
    generated_at: datetime
    cached: bool = False
