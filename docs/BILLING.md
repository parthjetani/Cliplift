# Billing System

Backend: `backend/app/billing/`. Stripe subscriptions with mock-first pattern. Hard cutoff on cancellation, no grace period.

## Plan Tiers

Source of truth: `billing/plans.py` `PLAN_LIMITS` dict (not DB columns).

| Limit | Creator ($29/mo) | Team ($79/mo) | Agency ($149/mo) |
|---|---|---|---|
| Tracked creators | 3 | 25 | 50 |
| Seats (max_users) | 1 | 5 | 25 |
| Platform connections | 1 | 4 | 4 |
| Scheduling | No | Yes | Yes |
| API access | No | No | Yes |
| Annual price | $244/yr (30% off) | $664/yr | $1,252/yr |

Valid plan values: `creator`, `team`, `agency`, `cancelled`. The `cancelled` plan has no entry in `PLAN_LIMITS` — enforcement hard-blocks it before any limit lookup.

`next_plan_up(plan)` returns the next tier in `PLAN_ORDER = ["creator", "team", "agency"]`. Used in 402 upgrade prompts. Returns `None` for agency, returns `"creator"` for cancelled/unknown.

## Mock-First Pattern

Same pattern as `ai/factory.py` and `common/storage.py`.

```
build_stripe_client(settings) → StripeClient
  ├─ STRIPE_SECRET_KEY set   → RealStripeClient (real Stripe SDK)
  └─ STRIPE_SECRET_KEY empty → MockStripeClient (deterministic, no API calls)
```

**`StripeClient` Protocol** (`billing/base.py`):

| Method | Returns |
|---|---|
| `create_checkout_session(...)` | `CheckoutResult(session_id, checkout_url)` |
| `create_billing_portal_session(...)` | `PortalResult(portal_url)` |
| `verify_webhook_signature(payload, sig_header)` | Raw event `dict` |
| `parse_billing_event(raw_event)` | `BillingEvent(event_type, team_id, plan, subscription_id, customer_id)` |

**MockStripeClient** (`billing/mock.py`):

- Checkout session IDs are deterministic: `mock_cs_{md5(team_id:plan:billing_period)[:12]}`.
- Webhook verification accepts any payload when `sig_header == "mock-signature"`.
- `build_synthetic_event()` static method builds fake webhook payloads for tests.

**RealStripeClient** (`billing/real.py`):

- All `stripe` SDK calls wrapped in `asyncio.to_thread()` (SDK is synchronous).
- Requires env vars: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_CREATOR`, `STRIPE_PRICE_TEAM`, `STRIPE_PRICE_AGENCY`.
- Sets `metadata.team_id` and `metadata.plan` on both the session and `subscription_data` so webhooks can resolve the team.

The client is stashed on `app.state.stripe_client` during lifespan and injected via `get_stripe_client` dependency in routes.

## Checkout Flow

```
Frontend                    Backend                         Stripe
   │                           │                               │
   ├─ POST /billing/checkout ──►                               │
   │  {plan, billing_period}   │                               │
   │                           ├─ create_checkout_session() ───►
   │                           │  (metadata: team_id, plan)    │
   │  ◄── {checkout_url} ─────┤                               │
   │                           │                               │
   ├─ redirect to checkout_url ───────────────────────────────►│
   │                           │                               │
   │  (user pays)              │                               │
   │                           │                               │
   │  ◄─── redirect to ───────────────────────────────────────┤
   │  /dashboard/settings/     │                               │
   │  billing?checkout=success │                               │
   │                           │                               │
   │                           │  ◄── POST /billing/webhook ──┤
   │                           │  (checkout.session.completed) │
   │                           │                               │
   │                           ├─ flip team.plan               │
   │                           ├─ set stripe_customer_id       │
   │                           ├─ set stripe_subscription_id   │
   │                           ├─ clear trial_ends_at          │
   │                           │                               │
```

**Request schema** (`CheckoutSessionRequest`):

```python
plan: Literal["creator", "team", "agency"]
billing_period: Literal["monthly", "annual"] = "monthly"
```

**Response** (`CheckoutSessionResponse`): `checkout_url` + `session_id`.

Success/cancel URLs point to `/dashboard/settings/billing?checkout=success|cancelled`.

## Webhook Handler

`POST /billing/webhook` — no auth. Stripe signs the request; signature verified via `verify_webhook_signature()`.

### Dispatch Table

| Event Type | Handler | DB Mutations |
|---|---|---|
| `checkout.session.completed` | `_handle_checkout_completed` | `team.plan = event.plan`, `team.stripe_customer_id = event.customer_id`, `team.stripe_subscription_id = event.subscription_id`, `team.trial_ends_at = None` |
| `customer.subscription.updated` | `_handle_subscription_updated` | `team.plan = event.plan`, `team.stripe_subscription_id = event.subscription_id` |
| `customer.subscription.deleted` | `_handle_subscription_deleted` | `team.plan = "cancelled"`, `team.trial_ends_at = None` |
| Anything else | Ignored | None (logged at DEBUG) |

Team resolution: `event.team_id` (from Stripe metadata) is parsed as UUID and looked up in the `teams` table.

### checkout.session.completed

Fires after successful payment. Flips the plan, stores Stripe IDs, clears trial. The plan value comes from `metadata.plan` set during checkout session creation.

### customer.subscription.updated

Fires on upgrade/downgrade via the Stripe Billing Portal. Updates plan and subscription ID. Does NOT touch `trial_ends_at`.

### customer.subscription.deleted

HARD CUTOFF. Sets `team.plan = "cancelled"` and clears `trial_ends_at`. Keeps `stripe_customer_id` and `stripe_subscription_id` for record-keeping and reactivation.

There is no grace period, no "cancelled but active until end of billing period." Cancelled means blocked immediately.

## Customer Portal

`POST /billing/portal` — returns a `portal_url` for the Stripe Billing Portal (manage subscription, upgrade/downgrade, cancel). Requires `team.stripe_customer_id` to exist (i.e., the team must have completed checkout at least once). Returns 400 otherwise.

## Cancellation Semantics

Two paths to a blocked account:

### 1. Stripe cancellation (subscription.deleted webhook)

```
team.plan = "cancelled"
team.trial_ends_at = None
```

`require_active_plan` checks `team.plan == "cancelled"` and returns 402.

### 2. Trial expiry (never-paid users)

No webhook fires for trial expiry — there's no Stripe subscription to delete. Instead, `require_active_plan` computes this on every write request:

```python
if (
    team.trial_ends_at is not None
    and team.trial_ends_at <= datetime.now(timezone.utc)
    and not team.stripe_subscription_id  # never paid
):
    raise PlanLimitExceeded(...)  # 402
```

This means trial-expired teams keep their plan name (e.g., `"creator"`) but are blocked from writes until they pay. Read-only endpoints remain accessible.

## Plan Enforcement

### require_active_plan

FastAPI dependency that replaces `get_current_team` on all write endpoints (POST/PUT/PATCH/DELETE). Read endpoints keep using `get_current_team` directly.

Checks in order:
1. `team.plan == "cancelled"` -> 402
2. `trial_ends_at` expired AND no `stripe_subscription_id` -> 402

Returns the `Team` if active.

### Per-Limit enforce_* Functions

Called explicitly inside route handlers after `require_active_plan` has passed.

| Function | What It Checks | Failure |
|---|---|---|
| `enforce_creator_tracking_limit(db, team)` | `COUNT(creator_tracking) >= limits.tracked_creators` | 402 with upgrade prompt |
| `enforce_platform_connection_limit(db, team)` | `COUNT(DISTINCT platform_connections.platform) >= limits.max_platforms` | 402 with upgrade prompt |
| `enforce_scheduling_enabled(team)` | `limits.scheduling == False` | 402, suggests Team plan |

All raise `PlanLimitExceeded` (HTTP 402 Payment Required) with:
- `detail`: Human-readable message with current limit and suggested upgrade
- `limit_name`: Machine-readable limit identifier
- `current_plan`: The team's current plan
- `suggested_plan`: Output of `next_plan_up()`, or hardcoded for scheduling

### Usage Pattern

```python
@router.post("/track")
async def track_creator(
    team: Annotated[Team, Depends(require_active_plan)],  # gate 1: active plan
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await enforce_creator_tracking_limit(db, team)         # gate 2: tier limit
    ...
```

### Endpoint Gating Summary

| Endpoint Type | Dependency | Additional Checks |
|---|---|---|
| Read (GET) | `get_current_team` | None — reads are never blocked |
| Write (POST/PUT/PATCH/DELETE) | `require_active_plan` | Per-limit `enforce_*` as needed |
| Billing routes (`/checkout`, `/portal`) | `get_current_team` / `get_current_profile` | No plan gate (must be accessible to upgrade) |
| Webhook (`/billing/webhook`) | None (Stripe signature only) | N/A |

## Env Vars

| Variable | Required For | Description |
|---|---|---|
| `STRIPE_SECRET_KEY` | RealStripeClient | Stripe API secret key. Empty = MockStripeClient. |
| `STRIPE_WEBHOOK_SECRET` | RealStripeClient | Webhook endpoint signing secret |
| `STRIPE_PRICE_CREATOR` | RealStripeClient | Stripe Price ID for Creator plan |
| `STRIPE_PRICE_TEAM` | RealStripeClient | Stripe Price ID for Team plan |
| `STRIPE_PRICE_AGENCY` | RealStripeClient | Stripe Price ID for Agency plan |

All five must be set for real Stripe. If `STRIPE_SECRET_KEY` is empty, all others are ignored and `MockStripeClient` is used.

## File Map

| File | Purpose |
|---|---|
| `billing/plans.py` | `PLAN_LIMITS` dict, `PlanLimits` model, `next_plan_up()` |
| `billing/base.py` | `StripeClient` Protocol, `CheckoutResult`, `PortalResult`, `BillingEvent` |
| `billing/mock.py` | `MockStripeClient` — deterministic, test-friendly |
| `billing/real.py` | `RealStripeClient` — wraps `stripe` SDK via `asyncio.to_thread()` |
| `billing/factory.py` | `build_stripe_client()` — picks real vs mock |
| `billing/schemas.py` | `CheckoutSessionRequest`, `CheckoutSessionResponse`, `BillingPortalResponse` |
| `billing/service.py` | `create_checkout_session`, `create_billing_portal_session`, `handle_webhook_event` |
| `billing/routes.py` | `POST /billing/checkout`, `POST /billing/portal`, `POST /billing/webhook` |
| `billing/enforcement.py` | `require_active_plan`, `enforce_*` functions, `PlanLimitExceeded` |
