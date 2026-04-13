"""Pydantic schemas for billing endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CheckoutSessionRequest(BaseModel):
    """Body for POST /billing/checkout."""

    plan: Literal["creator", "team", "agency"]
    billing_period: Literal["monthly", "annual"] = "monthly"


class CheckoutSessionResponse(BaseModel):
    """Returned from POST /billing/checkout."""

    checkout_url: str
    session_id: str


class BillingPortalResponse(BaseModel):
    """Returned from POST /billing/portal."""

    portal_url: str
