"""enable RLS on all public tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-22

Supabase exposes the `public` schema to PostgREST automatically, so any table
without RLS is reachable via anon/authenticated keys. Cliplift's FastAPI
backend connects as the `postgres` / service_role user, which bypasses RLS,
so enabling RLS with no policies is effectively deny-by-default for PostgREST
without impacting the app.

Covers the 13 app tables plus Alembic's own `alembic_version` bookkeeping
table.

`ALTER TABLE ... ENABLE ROW LEVEL SECURITY` is idempotent at the DB level —
safe against partially-applied prod state from the Supabase SQL Editor.
"""

from alembic import op


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


TABLES = (
    "alembic_version",
    "profiles",
    "teams",
    "team_members",
    "creators",
    "creator_trackings",
    "creator_snapshots",
    "videos",
    "video_snapshots",
    "video_trackings",
    "niches",
    "niche_videos",
    "platform_connections",
    "scheduled_posts",
    "post_analytics",
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
