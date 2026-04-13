"""Niche / trend discovery models."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base import CreatedAtMixin, UUIDMixin
from app.database import Base
from app.videos.models import Video

if TYPE_CHECKING:
    pass


class Niche(UUIDMixin, CreatedAtMixin, Base):
    """A user-defined topic for ongoing trend discovery.

    The auto-discovery worker periodically searches each niche's keywords across
    its target platforms and stores results in `niche_videos`.
    """

    __tablename__ = "niches"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    platforms: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default="{youtube,instagram,linkedin,tiktok}",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    niche_videos: Mapped[list["NicheVideo"]] = relationship(
        back_populates="niche", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Niche {self.name} platforms={self.platforms}>"


class NicheVideo(UUIDMixin, Base):
    """Many-to-many: a video discovered within a niche, with its niche-relative outlier score.

    Note: this score is *niche-relative* (Z-score vs all videos in this niche),
    not creator-relative (which lives on Video.outlier_score). Both are useful.
    """

    __tablename__ = "niche_videos"
    __table_args__ = (
        UniqueConstraint("niche_id", "video_id", name="uq_niche_videos_niche_video"),
    )

    niche_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("niches.id", ondelete="CASCADE"),
        nullable=False,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )
    outlier_score: Mapped[float | None] = mapped_column(
        Float, comment="Z-score vs niche baseline (median views in niche)"
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    # Relationships
    niche: Mapped[Niche] = relationship(back_populates="niche_videos")
    video: Mapped[Video] = relationship()
