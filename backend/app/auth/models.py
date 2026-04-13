"""Auth models — Profile (extends Supabase auth.users), Team, TeamMember.

The `profiles` table has a 1:1 relationship with `auth.users` (managed by
Supabase). The FK + auto-creation trigger are added via raw SQL in the initial
Alembic migration since Alembic doesn't see the `auth` schema.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base import CreatedAtMixin, TimestampMixin, UUIDMixin
from app.database import Base

if TYPE_CHECKING:
    from app.publishing.models import PlatformConnection, ScheduledPost


class Profile(TimestampMixin, Base):
    """User profile — extends Supabase auth.users.

    The `id` matches the auth.users.id, and a database trigger
    (see migration 0001) auto-creates a profile row on user signup.
    """

    __tablename__ = "profiles"

    # No SQLAlchemy FK to auth.users — added via raw SQL in migration
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True)

    # Relationships
    owned_teams: Mapped[list["Team"]] = relationship(
        back_populates="owner", foreign_keys="[Team.owner_id]"
    )
    team_memberships: Mapped[list["TeamMember"]] = relationship(
        back_populates="user", foreign_keys="[TeamMember.user_id]"
    )

    def __repr__(self) -> str:
        return f"<Profile {self.email}>"


class Team(UUIDMixin, CreatedAtMixin, Base):
    """A workspace owned by one user, optionally shared with team members."""

    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Subscription
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="creator")
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, comment="Stripe Customer ID (cus_...)"
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, comment="Stripe Subscription ID (sub_...)"
    )

    # Trial — new teams get 7 days; enforcement blocks writes when
    # trial_ends_at < now() AND stripe_subscription_id IS NULL (never paid)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Legacy per-row limits (superseded by PLAN_LIMITS in billing/plans.py)
    max_tracked_creators: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    max_seats: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Relationships
    owner: Mapped[Profile] = relationship(
        back_populates="owned_teams", foreign_keys=[owner_id]
    )
    members: Mapped[list["TeamMember"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Team {self.name} ({self.plan})>"


class TeamMember(UUIDMixin, Base):
    """Membership linking a Profile to a Team with a role."""

    __tablename__ = "team_members"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")

    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    team: Mapped[Team] = relationship(back_populates="members")
    user: Mapped[Profile] = relationship(
        back_populates="team_memberships", foreign_keys=[user_id]
    )

    def __repr__(self) -> str:
        return f"<TeamMember user={self.user_id} team={self.team_id} role={self.role}>"
