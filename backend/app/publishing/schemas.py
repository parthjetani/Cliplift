"""Pydantic schemas for the publishing module — presign + scheduled posts."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.platforms.base import Platform

# ----------------------------------------------------------------------------
# Status enum (string-valued so it serializes cleanly)
# ----------------------------------------------------------------------------


class PostStatus(str, Enum):
    """Lifecycle of a scheduled post."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


# ----------------------------------------------------------------------------
# Presign
# ----------------------------------------------------------------------------


# Allowed MIME types for video uploads. Using Literal so Pydantic emits a
# clean `literal_error` on mismatch (no raw exceptions in the error context).
AllowedVideoType = Literal[
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-m4v",
]


class PresignRequest(BaseModel):
    """Body for `POST /publishing/uploads/presign`."""

    # Filename must be 1..255 chars, no path separators, no leading dot.
    # `pattern` runs in Pydantic core (no Python validator), so the resulting
    # error is JSON-serializable without special handling.
    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=r"^[^/\\.][^/\\]*$",
        description="Video filename (no path separators, no leading dot)",
    )
    content_type: AllowedVideoType = Field(
        ...,
        description="MIME type of the file to upload",
    )


class PresignResponse(BaseModel):
    """Returned from `POST /publishing/uploads/presign`."""

    upload_url: str
    file_key: str
    expires_at: datetime


# ----------------------------------------------------------------------------
# Scheduled post CRUD
# ----------------------------------------------------------------------------


class ScheduledPostCreate(BaseModel):
    """Body for `POST /publishing/scheduled-posts`."""

    connection_id: uuid.UUID
    platform: Platform
    file_key: str = Field(..., min_length=1, max_length=512)
    title: str | None = Field(default=None, max_length=512)
    description: str | None = None
    hashtags: list[str] | None = Field(default=None, max_length=30)
    scheduled_for: datetime
    inspired_by_video_id: uuid.UUID | None = None


class ScheduledPostUpdate(BaseModel):
    """Body for `PATCH /publishing/scheduled-posts/{id}`.

    `connection_id`, `platform`, and `file_key` are locked once a post is
    created — to change them, delete and create a new post.
    """

    title: str | None = Field(default=None, max_length=512)
    description: str | None = None
    hashtags: list[str] | None = Field(default=None, max_length=30)
    scheduled_for: datetime | None = None
    inspired_by_video_id: uuid.UUID | None = None
    status: PostStatus | None = None


class ScheduledPostResponse(BaseModel):
    """Public shape of a `ScheduledPost` row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    team_id: uuid.UUID
    connection_id: uuid.UUID
    created_by: uuid.UUID | None = None
    inspired_by_video_id: uuid.UUID | None = None

    platform: Platform
    title: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None
    file_key: str | None = None
    media_url: str | None = None

    scheduled_for: datetime
    status: PostStatus
    platform_post_id: str | None = None
    error_message: str | None = None
    published_at: datetime | None = None

    created_at: datetime
    updated_at: datetime
