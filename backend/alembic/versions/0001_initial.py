"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-08

Creates all 13 application tables, indexes, the FK from profiles → auth.users,
and the trigger that auto-creates a profile row when a Supabase user signs up.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ==========================================================================
    # AUTH & ACCOUNTS
    # ==========================================================================

    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("stripe_customer_id"),
    )

    # FK profiles.id → auth.users.id (raw SQL — Alembic doesn't manage auth schema)
    op.execute(
        """
        ALTER TABLE profiles
        ADD CONSTRAINT fk_profiles_auth_users
        FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE
        """
    )

    op.create_table(
        "teams",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False, server_default="creator"),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("max_tracked_creators", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("max_seats", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_subscription_id"),
    )

    op.create_table(
        "team_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column(
            "invited_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ==========================================================================
    # CREATORS
    # ==========================================================================

    op.create_table(
        "creators",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("platform_id", sa.String(255), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "platform_id", name="uq_creators_platform_id"),
    )

    op.create_table(
        "creator_trackings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "tracked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "creator_id", name="uq_creator_trackings_team_creator"),
    )

    op.create_table(
        "creator_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("followers", sa.Integer(), nullable=True),
        sa.Column("total_videos", sa.Integer(), nullable=True),
        sa.Column("avg_views_30d", sa.Float(), nullable=True),
        sa.Column("avg_engagement_30d", sa.Float(), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_id", "snapshot_date", name="uq_creator_snapshots_date"),
    )

    # ==========================================================================
    # VIDEOS
    # ==========================================================================

    op.create_table(
        "videos",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("platform_video_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.String(512), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hashtags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("is_short", sa.Boolean(), nullable=False, server_default=sa.true()),
        # Outlier flags
        sa.Column("outlier_score", sa.Float(), nullable=True),
        sa.Column("is_outlier", sa.Boolean(), nullable=False, server_default=sa.false()),
        # Denormalized latest metrics (BIGINT for viral videos > 2.1B views)
        sa.Column("latest_views", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("latest_likes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("latest_comments", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("latest_shares", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("latest_engagement_rate", sa.Float(), nullable=True),
        sa.Column("latest_snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "platform_video_id", name="uq_videos_platform_id"),
    )

    op.create_table(
        "video_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("views", sa.BigInteger(), nullable=True),
        sa.Column("likes", sa.BigInteger(), nullable=True),
        sa.Column("comments", sa.BigInteger(), nullable=True),
        sa.Column("shares", sa.BigInteger(), nullable=True),
        sa.Column("engagement_rate", sa.Float(), nullable=True),
        sa.Column("view_velocity", sa.Float(), nullable=True),
        sa.Column(
            "snapshot_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "video_trackings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "tracked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "video_id", name="uq_video_trackings_team_video"),
    )

    # ==========================================================================
    # NICHE / DISCOVERY
    # ==========================================================================

    op.create_table(
        "niches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column(
            "platforms",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{youtube,instagram,linkedin,tiktok}",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "niche_videos",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("niche_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outlier_score", sa.Float(), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("niche_id", "video_id", name="uq_niche_videos_niche_video"),
    )

    # ==========================================================================
    # PUBLISHING
    # ==========================================================================

    op.create_table(
        "platform_connections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("platform_user_id", sa.String(255), nullable=True),
        sa.Column("platform_username", sa.String(255), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "scheduled_posts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("inspired_by_video_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("hashtags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("file_key", sa.String(512), nullable=True),
        sa.Column("media_url", sa.String(1024), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("platform_post_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["platform_connections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["inspired_by_video_id"], ["videos.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "post_analytics",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("views", sa.BigInteger(), nullable=True),
        sa.Column("likes", sa.BigInteger(), nullable=True),
        sa.Column("comments", sa.BigInteger(), nullable=True),
        sa.Column("shares", sa.BigInteger(), nullable=True),
        sa.Column("watch_time_seconds", sa.BigInteger(), nullable=True),
        sa.Column("avg_view_duration", sa.Float(), nullable=True),
        sa.Column(
            "snapshot_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["post_id"], ["scheduled_posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ==========================================================================
    # INDEXES (critical for performance)
    # ==========================================================================

    op.create_index(
        "idx_videos_platform_published",
        "videos",
        ["platform", sa.text("published_at DESC")],
    )
    op.create_index(
        "idx_video_snapshots_video_time",
        "video_snapshots",
        ["video_id", sa.text("snapshot_at DESC")],
    )
    op.create_index(
        "idx_creator_snapshots_creator_date",
        "creator_snapshots",
        ["creator_id", sa.text("snapshot_date DESC")],
    )
    op.create_index(
        "idx_niche_videos_niche_score",
        "niche_videos",
        ["niche_id", sa.text("outlier_score DESC")],
    )
    op.create_index(
        "idx_scheduled_posts_team_status",
        "scheduled_posts",
        ["team_id", "status", "scheduled_for"],
    )
    op.create_index("idx_creators_platform", "creators", ["platform", "platform_id"])
    op.create_index(
        "idx_videos_outlier",
        "videos",
        ["platform", "is_outlier", sa.text("latest_engagement_rate DESC")],
    )
    op.create_index(
        "idx_videos_creator_views",
        "videos",
        ["creator_id", sa.text("latest_views DESC")],
    )

    # ==========================================================================
    # PROFILE AUTO-CREATION TRIGGER
    # When a user signs up via Supabase Auth, auto-create their profile row.
    # Without this, the first API call after signup fails with FK error.
    # ==========================================================================

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.handle_new_user()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        BEGIN
            INSERT INTO public.profiles (id, email, created_at, updated_at)
            VALUES (NEW.id, NEW.email, now(), now())
            ON CONFLICT (id) DO NOTHING;
            RETURN NEW;
        END;
        $$;
        """
    )

    # asyncpg requires one statement per execute() call (no multi-statement prepared statements)
    op.execute("DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users")
    op.execute(
        """
        CREATE TRIGGER on_auth_user_created
            AFTER INSERT ON auth.users
            FOR EACH ROW
            EXECUTE FUNCTION public.handle_new_user()
        """
    )


def downgrade() -> None:
    # Drop trigger first (depends on auth.users)
    op.execute("DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users")
    op.execute("DROP FUNCTION IF EXISTS public.handle_new_user()")

    # Drop indexes
    op.drop_index("idx_videos_creator_views", table_name="videos")
    op.drop_index("idx_videos_outlier", table_name="videos")
    op.drop_index("idx_creators_platform", table_name="creators")
    op.drop_index("idx_scheduled_posts_team_status", table_name="scheduled_posts")
    op.drop_index("idx_niche_videos_niche_score", table_name="niche_videos")
    op.drop_index("idx_creator_snapshots_creator_date", table_name="creator_snapshots")
    op.drop_index("idx_video_snapshots_video_time", table_name="video_snapshots")
    op.drop_index("idx_videos_platform_published", table_name="videos")

    # Drop tables in reverse dependency order
    op.drop_table("post_analytics")
    op.drop_table("scheduled_posts")
    op.drop_table("platform_connections")
    op.drop_table("niche_videos")
    op.drop_table("niches")
    op.drop_table("video_trackings")
    op.drop_table("video_snapshots")
    op.drop_table("videos")
    op.drop_table("creator_snapshots")
    op.drop_table("creator_trackings")
    op.drop_table("creators")
    op.drop_table("team_members")
    op.drop_table("teams")

    # Drop FK before dropping profiles (depends on auth.users)
    op.execute("ALTER TABLE profiles DROP CONSTRAINT IF EXISTS fk_profiles_auth_users")
    op.drop_table("profiles")
