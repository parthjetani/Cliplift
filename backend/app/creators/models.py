"""Creator tracking models."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base import CreatedAtMixin, UUIDMixin
from app.database import Base

if TYPE_CHECKING:
    from app.videos.models import Video


class Creator(UUIDMixin, CreatedAtMixin, Base):
    """A creator on a single platform.

    Same person on different platforms = different Creator rows. Cross-platform
    linking happens at a higher level via display_name + bio matching.
    """

    __tablename__ = "creators"
    __table_args__ = (
        UniqueConstraint("platform", "platform_id", name="uq_creators_platform_id"),
    )

    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_id: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    bio: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    snapshots: Mapped[list["CreatorSnapshot"]] = relationship(
        back_populates="creator", cascade="all, delete-orphan"
    )
    trackings: Mapped[list["CreatorTracking"]] = relationship(
        back_populates="creator", cascade="all, delete-orphan"
    )
    videos: Mapped[list["Video"]] = relationship(back_populates="creator")

    def __repr__(self) -> str:
        return f"<Creator {self.platform}:{self.username or self.platform_id}>"


class CreatorTracking(UUIDMixin, Base):
    """Many-to-many between Team and Creator (a team is following a creator)."""

    __tablename__ = "creator_trackings"
    __table_args__ = (
        UniqueConstraint("team_id", "creator_id", name="uq_creator_trackings_team_creator"),
    )

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=False,
    )
    tracked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    creator: Mapped[Creator] = relationship(back_populates="trackings")


class CreatorSnapshot(UUIDMixin, Base):
    """Daily snapshot of a creator's metrics for trend analysis."""

    __tablename__ = "creator_snapshots"
    __table_args__ = (
        UniqueConstraint("creator_id", "snapshot_date", name="uq_creator_snapshots_date"),
    )

    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=False,
    )
    followers: Mapped[int | None] = mapped_column(Integer)
    total_videos: Mapped[int | None] = mapped_column(Integer)
    avg_views_30d: Mapped[float | None] = mapped_column(Float)
    avg_engagement_30d: Mapped[float | None] = mapped_column(Float)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Relationships
    creator: Mapped[Creator] = relationship(back_populates="snapshots")
