"""Video tracking models.

`videos.latest_*` are denormalized from the most recent VideoSnapshot to avoid
joins on every dashboard query. Updated by the snapshot worker.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base import CreatedAtMixin, UUIDMixin
from app.creators.models import Creator
from app.database import Base

if TYPE_CHECKING:
    from app.discovery.models import NicheVideo
    from app.publishing.models import ScheduledPost


class Video(UUIDMixin, CreatedAtMixin, Base):
    """A short-form video on a platform."""

    __tablename__ = "videos"
    __table_args__ = (
        UniqueConstraint("platform", "platform_video_id", name="uq_videos_platform_id"),
    )

    creator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creators.id", ondelete="SET NULL"),
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_video_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(String(512))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hashtags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    is_short: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- Outlier flags (creator-relative) ---
    outlier_score: Mapped[float | None] = mapped_column(
        Float, comment="Creator-relative Z-score (views vs creator's median)"
    )
    is_outlier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Denormalized latest metrics (avoid joins on dashboard queries) ---
    latest_views: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    latest_likes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    latest_comments: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    latest_shares: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    latest_engagement_rate: Mapped[float | None] = mapped_column(Float)
    latest_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    creator: Mapped[Creator | None] = relationship(back_populates="videos")
    snapshots: Mapped[list["VideoSnapshot"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    trackings: Mapped[list["VideoTracking"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Video {self.platform}:{self.platform_video_id} views={self.latest_views}>"


class VideoSnapshot(UUIDMixin, Base):
    """A point-in-time snapshot of a video's metrics.

    Append-only table — used to compute view velocity, growth curves, etc.
    BIGINT used because viral videos can exceed INT max (2.1 billion views).
    """

    __tablename__ = "video_snapshots"

    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )
    views: Mapped[int | None] = mapped_column(BigInteger)
    likes: Mapped[int | None] = mapped_column(BigInteger)
    comments: Mapped[int | None] = mapped_column(BigInteger)
    shares: Mapped[int | None] = mapped_column(BigInteger)
    engagement_rate: Mapped[float | None] = mapped_column(Float)
    view_velocity: Mapped[float | None] = mapped_column(
        Float, comment="Views per hour since previous snapshot"
    )
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Relationships
    video: Mapped[Video] = relationship(back_populates="snapshots")


class VideoTracking(UUIDMixin, Base):
    """Many-to-many between Team and Video."""

    __tablename__ = "video_trackings"
    __table_args__ = (
        UniqueConstraint("team_id", "video_id", name="uq_video_trackings_team_video"),
    )

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )
    tracked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    # Relationships
    video: Mapped[Video] = relationship(back_populates="trackings")
