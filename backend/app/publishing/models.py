"""Publishing models — OAuth connections, scheduled posts, post analytics."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base import CreatedAtMixin, TimestampMixin, UUIDMixin
from app.database import Base
from app.videos.models import Video

if TYPE_CHECKING:
    pass


class PlatformConnection(UUIDMixin, CreatedAtMixin, Base):
    """An OAuth connection to a publishing platform (YouTube, Instagram, etc.).

    Tokens are AES-256 encrypted at the application layer (cryptography.fernet)
    before being stored. The DB only sees ciphertext.
    """

    __tablename__ = "platform_connections"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_user_id: Mapped[str | None] = mapped_column(String(255))
    platform_username: Mapped[str | None] = mapped_column(String(255))

    # Encrypted at app layer (Fernet)
    access_token: Mapped[str | None] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    # Relationships
    scheduled_posts: Mapped[list["ScheduledPost"]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PlatformConnection {self.platform}:{self.platform_username}>"


class ScheduledPost(UUIDMixin, TimestampMixin, Base):
    """A post scheduled to publish to a platform at a specific time.

    Status flow: draft → scheduled → publishing → published / failed
    """

    __tablename__ = "scheduled_posts"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Audit trail — who in the team created this
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
    )
    # Insight → action link: the outlier video that inspired this post
    inspired_by_video_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="SET NULL"),
    )

    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # File: stored in Supabase Storage via presigned upload, never touches our server
    file_key: Mapped[str | None] = mapped_column(
        String(512), comment="Supabase Storage object key"
    )
    media_url: Mapped[str | None] = mapped_column(
        String(1024), comment="Public URL (generated from file_key at publish time)"
    )

    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    platform_post_id: Mapped[str | None] = mapped_column(
        String(255), comment="Set after successful publish"
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    connection: Mapped[PlatformConnection] = relationship(back_populates="scheduled_posts")
    inspired_by_video: Mapped[Video | None] = relationship()
    analytics: Mapped[list["PostAnalytics"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ScheduledPost {self.platform} {self.status} @ {self.scheduled_for}>"


class PostAnalytics(UUIDMixin, Base):
    """Snapshot of a published post's performance metrics."""

    __tablename__ = "post_analytics"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    views: Mapped[int | None] = mapped_column(BigInteger)
    likes: Mapped[int | None] = mapped_column(BigInteger)
    comments: Mapped[int | None] = mapped_column(BigInteger)
    shares: Mapped[int | None] = mapped_column(BigInteger)
    watch_time_seconds: Mapped[int | None] = mapped_column(BigInteger)
    avg_view_duration: Mapped[float | None] = mapped_column(Float)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Relationships
    post: Mapped[ScheduledPost] = relationship(back_populates="analytics")
