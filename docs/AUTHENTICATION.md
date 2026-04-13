# Authentication

Backend auth for Cliplift. Supabase owns user registration and login; FastAPI only validates JWTs and manages the `profiles`/`teams` rows that extend the Supabase `auth.users` table.

## JWT Validation

`app/auth/middleware.py` handles token verification. Two signing modes are supported:

**HS256 (symmetric)** -- older Supabase projects. Uses `SUPABASE_JWT_SECRET` from env.

**ES256/RS256 (asymmetric)** -- newer projects. Public key fetched from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` via `PyJWKClient` (cached 1 hour).

The algorithm is auto-detected from the token header's `alg` field -- no config needed.

Required claims: `sub`, `email`, `exp`. Audience must be `"authenticated"`.

```python
# middleware.py -- simplified flow
header = jwt.get_unverified_header(token)
if header["alg"] == "HS256":
    payload = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")
elif header["alg"] in ("ES256", "RS256"):
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    payload = jwt.decode(token, signing_key.key, algorithms=[alg], audience="authenticated")
```

The decoded payload is returned as a `SupabaseUser(id, email, role, aud)` Pydantic model.

`extract_bearer_token()` splits the `Authorization: Bearer <token>` header. Missing or malformed headers raise `JWTValidationError` (HTTP 401 with `WWW-Authenticate: Bearer`).

## Dependency Chain

Three FastAPI dependencies, each building on the previous:

```
get_current_user  -->  get_current_profile  -->  get_current_team
   (JWT only)           (+ DB profile)            (+ DB team)
```

### `get_current_user`

Extracts and validates the JWT. Returns `SupabaseUser`. No DB call.

```python
async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> SupabaseUser:
    token = extract_bearer_token(authorization)
    return decode_supabase_jwt(token)
```

Use when you only need the user's UUID/email and don't need profile or team data.

### `get_current_profile`

Depends on `get_current_user`. Fetches (or creates) the `Profile` row.

```python
async def get_current_profile(
    user: Annotated[SupabaseUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Profile:
    return await get_or_create_profile(db, user.id, user.email)
```

### `get_current_team`

Depends on `get_current_profile`. Fetches (or creates) the user's default `Team`.

```python
async def get_current_team(
    profile: Annotated[Profile, Depends(get_current_profile)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Team:
    return await get_or_create_default_team(db, profile)
```

This is the standard dependency for **read** endpoints that operate on team-scoped data (creators, videos, niches, posts, connections).

## Auto-Creation on First API Call

Both Profile and Team are created lazily on first authenticated request. No separate onboarding step required.

### Profile

Supabase has a DB trigger (`on_auth_user_created`) that inserts into `profiles` on signup. `get_or_create_profile` handles two edge cases:

1. **Race condition** -- API call arrives before the trigger fires
2. **Legacy user** -- existed before the trigger was deployed

On conflict (trigger fires during our INSERT), the service catches the exception, rolls back, and re-fetches.

### Team

Every user gets exactly one auto-created "Personal" team with:

| Field | Value |
|---|---|
| `name` | `"Personal"` |
| `plan` | `"creator"` |
| `trial_ends_at` | `now() + 7 days` |
| `max_tracked_creators` | `3` |
| `max_seats` | `1` |

Same idempotent pattern -- concurrent requests won't create duplicates.

Multi-team workspaces are Phase 2. For now, `get_default_team` returns the user's first owned team ordered by `created_at`.

## `require_active_plan` vs `get_current_team`

Both return a `Team`. The difference: `require_active_plan` blocks writes for expired/cancelled teams.

| Dependency | Use on | Behavior when expired |
|---|---|---|
| `get_current_team` | **GET** endpoints | Allows access (read-only is always free) |
| `require_active_plan` | **POST/PUT/PATCH/DELETE** | Raises 402 `PlanLimitExceeded` |

`require_active_plan` wraps `get_current_team` -- it calls it internally, then checks:

```python
async def require_active_plan(
    team: Annotated[Team, Depends(get_current_team)],
) -> Team:
    # Check 1: explicit cancellation
    if team.plan == "cancelled":
        raise PlanLimitExceeded(...)

    # Check 2: trial expired and never paid
    if (
        team.trial_ends_at is not None
        and team.trial_ends_at <= datetime.now(timezone.utc)
        and not team.stripe_subscription_id
    ):
        raise PlanLimitExceeded(...)

    return team
```

### Route usage

```python
# Read endpoint -- get_current_team is sufficient
@router.get("")
async def list_creators(
    team: Annotated[Team, Depends(get_current_team)],
):
    ...

# Write endpoint -- require_active_plan gates access
@router.post("/track")
async def track_creator(
    team: Annotated[Team, Depends(require_active_plan)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await enforce_creator_tracking_limit(db, team)
    ...
```

## Trial + Subscription Enforcement

The `Team` model carries two columns that drive billing enforcement:

```
trial_ends_at: datetime | None       -- set to now()+7d on team creation
stripe_subscription_id: str | None   -- set by Stripe webhook on first payment
```

State matrix:

| `trial_ends_at` | `stripe_subscription_id` | `plan` | Status |
|---|---|---|---|
| future | `NULL` | `"creator"` | Active trial |
| past | `NULL` | `"creator"` | **Blocked** -- trial expired, never paid |
| any | `"sub_..."` | `"creator"` | Paying customer |
| any | `"sub_..."` | `"cancelled"` | **Blocked** -- subscription cancelled via webhook |

The "never paid" check is computed on every write request because there's no Stripe event that fires when a trial simply expires. The `cancelled` state is set by a Stripe webhook when the subscription ends.

### Per-Tier Limits

After `require_active_plan` passes, individual limit checks can be called explicitly:

- `enforce_creator_tracking_limit(db, team)` -- checks tracked creators against plan cap
- `enforce_platform_connection_limit(db, team)` -- checks connected platforms against plan cap
- `enforce_scheduling_enabled(team)` -- checks if plan includes scheduling (Team/Agency only)

All raise `PlanLimitExceeded` (HTTP 402) with `limit_name`, `current_plan`, and `suggested_plan` in the response for the frontend to render upgrade prompts.

## Data Model

### Profile

Extends `auth.users`. The `id` column matches the Supabase user UUID (no SQLAlchemy FK -- added via raw SQL in migration).

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | = `auth.users.id` |
| `email` | `str(255)` unique | |
| `name` | `str(255)` nullable | |
| `avatar_url` | `str(512)` nullable | |
| `stripe_customer_id` | `str(255)` unique nullable | |

### Team

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | Auto-generated |
| `name` | `str(255)` | `"Personal"` for default team |
| `owner_id` | `UUID` FK -> `profiles.id` | CASCADE delete |
| `plan` | `str(32)` | `"creator"` / `"team"` / `"agency"` / `"cancelled"` |
| `stripe_customer_id` | `str(255)` unique nullable | |
| `stripe_subscription_id` | `str(255)` unique nullable | |
| `trial_ends_at` | `datetime(tz)` nullable | |
| `max_tracked_creators` | `int` | Legacy; superseded by `PLAN_LIMITS` |
| `max_seats` | `int` | Legacy; superseded by `PLAN_LIMITS` |

### TeamMember

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | |
| `team_id` | `UUID` FK -> `teams.id` | CASCADE delete |
| `user_id` | `UUID` FK -> `profiles.id` | CASCADE delete |
| `role` | `str(32)` | Default `"member"` |
| `invited_at` | `datetime(tz)` | Server default `now()` |
| `joined_at` | `datetime(tz)` nullable | |

## Key Files

| File | Purpose |
|---|---|
| `app/auth/middleware.py` | JWT decode + bearer extraction |
| `app/auth/dependencies.py` | FastAPI `Depends()` chain |
| `app/auth/service.py` | Profile/team CRUD + idempotent creation |
| `app/auth/models.py` | SQLAlchemy models (Profile, Team, TeamMember) |
| `app/auth/schemas.py` | Pydantic models (SupabaseUser, ProfileResponse, TeamResponse) |
| `app/billing/enforcement.py` | `require_active_plan` + per-tier limit gates |
| `app/billing/plans.py` | `PLAN_LIMITS` dict with per-tier caps |
