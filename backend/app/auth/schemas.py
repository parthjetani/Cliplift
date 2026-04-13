"""Pydantic schemas for the auth domain.

Note: we use plain `str` for emails (not `EmailStr`). Supabase already validates
email format on signup, and `EmailStr` rejects reserved TLDs (.test, .example,
.invalid) which makes integration testing painful. Trust Supabase as the source
of truth for email validity.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SupabaseUser(BaseModel):
    """Decoded Supabase JWT payload — what we extract from the token."""

    id: uuid.UUID = Field(..., description="auth.users.id (sub claim)")
    email: str
    role: str = "authenticated"
    aud: str = "authenticated"


class ProfileResponse(BaseModel):
    """Public profile shape returned to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str | None = None
    avatar_url: str | None = None
    stripe_customer_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ProfileUpdate(BaseModel):
    """Fields the user can update on their own profile."""

    name: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=512)


class TeamResponse(BaseModel):
    """Public shape of a Team row — returned from GET /teams/me."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    plan: str
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    trial_ends_at: datetime | None = None
    created_at: datetime

    # Computed fields — not stored in DB, derived at serialization time
    is_trial_active: bool = False
    is_trial_expired: bool = False

    def model_post_init(self, __context: object) -> None:
        """Compute trial flags from the raw row data."""
        if self.trial_ends_at is not None:
            from datetime import timezone

            now = datetime.now(timezone.utc)
            # Make trial_ends_at tz-aware if it isn't
            trial_end = self.trial_ends_at
            if trial_end.tzinfo is None:
                trial_end = trial_end.replace(tzinfo=timezone.utc)
            self.is_trial_active = trial_end > now
            self.is_trial_expired = (
                trial_end <= now and not self.stripe_subscription_id
            )
