"""team stripe_customer_id and trial_ends_at

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-11

Adds:
- teams.stripe_customer_id (unique, for Stripe checkout flow)
- teams.trial_ends_at (7-day trial countdown; enforcement blocks writes when
  trial_ends_at < now() AND stripe_subscription_id IS NULL — i.e., never paid)

Backfills trial_ends_at = now() + 7 days for all existing teams so they
behave like fresh signups.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add stripe_customer_id column
    op.add_column(
        "teams",
        sa.Column(
            "stripe_customer_id",
            sa.String(255),
            unique=True,
            nullable=True,
            comment="Stripe Customer ID (cus_...)",
        ),
    )

    # Add trial_ends_at column
    op.add_column(
        "teams",
        sa.Column(
            "trial_ends_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Backfill: existing teams get a 7-day trial from now
    op.execute(
        "UPDATE teams SET trial_ends_at = now() + interval '7 days' "
        "WHERE trial_ends_at IS NULL"
    )


def downgrade() -> None:
    op.drop_column("teams", "trial_ends_at")
    op.drop_column("teams", "stripe_customer_id")
