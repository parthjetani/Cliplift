# Lessons

Patterns captured after user corrections. Per `CLAUDE.md` → Self-Improvement Loop: append a lesson here every time the user corrects an approach, so the same mistake doesn't recur.

Format:

```
## <short title>
**Date:** YYYY-MM-DD
**Trigger:** <what I did that prompted the correction>
**Correction:** <what the user said to do instead>
**Rule:** <the durable rule for future sessions>
```

Review this file at the start of any new task in this repo.

---

## Don't ship one-line summaries when "task form" is requested

**Date:** 2026-04-11
**Trigger:** After Chunk 17 was done, I left Chunks 18–21 in `tasks/todo.md` as one-line bullet summaries under "Next up". User said "Make all chunk in tasks forms" — they wanted every chunk written out as a full pre-flight + implementation + tests + verification checklist, the same shape as Chunk 17.
**Correction:** User wanted ALL chunks expanded into checkable task lists immediately, not lazily as each one became active.
**Rule:** When the user references "task form" / "checklist" / "todo", default to fully expanded checklists for **every** chunk in scope, not just the active one. The point of `tasks/todo.md` is to be a contract the user can audit before code lands — one-line summaries hide too much. If a chunk plan exists in `synthetic-crafting-umbrella.md`, mirror its file list + verification steps as `- [ ]` items in `todo.md` from the start.

---

## When user says "the issue is another", stop guessing and instrument

**Date:** 2026-04-11
**Trigger:** During the E2E sweep, the Chrome MCP `find` tool returned "Cannot access contents of the page. Extension manifest must request permission to access the respective host." I assumed it was a Chrome extension permissions issue and asked the user to switch the access mode to "On all sites." User replied: "It's already 'On all Sites', permission is not changing everytime, I think issue is another." The actual problem was that the `find` tool's accessibility-tree path was failing for some other reason — `javascript_tool` worked fine on the same tab. Switching to JS-driven DOM queries unblocked the entire sweep.
**Correction:** User pushed back on my misdiagnosis and forced me to question the surface-level error message instead of trusting it.
**Rule:** When a tool returns an error message that points at a specific cause (permissions, missing config, etc.), **verify the cause with a different tool before asking the user to fix it**. Specifically for the Chrome MCP: if `find`/`read_page` fail with "cannot access contents", try `javascript_tool` with a simple expression like `({url: location.href, ready: document.readyState})` first — if JS works, the error message is misleading and the right move is to drive the rest of the test via JS, not to escalate to the user.

---

## Always check backend constraints before writing frontend pagination

**Date:** 2026-04-11
**Trigger:** Calendar page (Chunk 21) requested `?limit=200` from the scheduled-posts list endpoint. The chunk plan in `synthetic-crafting-umbrella.md` literally said "limit=200" and I copied it without checking the backend. The backend's `PaginationParams` enforces `le=100` (set in Week 1), so the call returned `422 Request validation failed` and the calendar showed an error in the browser sweep.
**Correction:** I had to fix this live during the E2E sweep by switching to cursor pagination (5 pages × 100). Bug only surfaced because the user insisted on running the sweep.
**Rule:** Before writing any frontend `?limit=N` query, grep the backend's `PaginationParams` / equivalent for the actual `le=` cap. Plan documents are not ground truth — the running code is. Same applies to any other validated query param: enums, date ranges, content_type allowlists. Backend Pydantic constraints are checked against the live source, not the plan.

---

## Mock-first means *every* layer mocked, not just the OAuth flow

**Date:** 2026-04-11
**Trigger:** Publisher factory in Chunk 18 always registered the real `YouTubeShortsPublisher` regardless of whether Google OAuth credentials were set. The OAuth provider correctly fell back to `MockOAuthProvider` when env vars were missing, but the publisher then used those mock tokens (`mock-access-...`) against the real `googleapis.com/upload/youtube/v3/videos` endpoint, which 401'd. I only caught this in the E2E sweep when the worker reported "YouTube upload failed (401): Request had invalid authentication credentials."
**Correction:** Self-corrected during the sweep — added `isinstance(oauth_provider, MockOAuthProvider)` check in the factory so YouTube + Instagram fall back to `MockPublisher` when their OAuth is mocked. Plus 4 new factory tests.
**Rule:** "Mock-first" is a chain of dependencies — if any link in the chain is mocked, every downstream consumer must also be mocked OR explicitly bypass the broken link. When writing a factory that depends on credentials from another factory, inspect the *type* of what you got back, not just whether you got something. Tests for the factory must cover both real and mock branches for every supported platform — see `test_publisher_factory.py` for the pattern (`test_X_real_when_credentials_set` AND `test_X_mock_when_credentials_missing`).

---

## When `useEffect`-on-`open` is what you want, don't reach for `onOpenChange`

**Date:** 2026-04-11
**Trigger:** `content-brief-dialog.tsx` (Chunk 15) wired the auto-fetch logic to a custom `handleOpenChange` callback passed to Radix `<Dialog onOpenChange>`. The brief modal opened (parent set `open={true}`) but the brief was never fetched, leaving the modal stuck on its loading shell. Radix only calls `onOpenChange` when *its own internal state* toggles (trigger click, Escape, click outside) — not when the parent flips a controlled `open` prop.
**Correction:** Self-corrected during the sweep — replaced the `handleOpenChange` shortcut with a `useEffect` keyed on `[open]` that calls `generate()` when `open && !brief && !isPending && !error`.
**Rule:** Radix `onOpenChange` is for *user-initiated* state transitions, not parent-controlled prop changes. If a dialog needs to do something when it becomes visible AND the parent controls `open` externally via `setOpen(true)`, use a `useEffect` keyed on the `open` prop. Same applies to any Radix primitive with a controlled `open`/`value` prop — the change-callback fires for internal transitions only. Generally: if you wrote `<X open={parentState} onOpenChange={...}>` and you want to react to `parentState` flipping to true, add a `useEffect`.

---

## Test fixtures that touch the engine must also dispose it

**Date:** 2026-04-11
**Trigger:** New `test_publish_worker.py` (Chunk 19) added a `db_session` fixture using `AsyncSessionLocal()`. First test run failed with "RuntimeError: Task got Future attached to a different loop" because asyncpg pool connections leaked across pytest event loops. The conftest `client` fixture handles this by calling `await engine.dispose()` in teardown — my new fixture didn't.
**Correction:** Self-corrected — added `await engine.dispose()` to the `db_session` fixture's teardown to mirror the conftest pattern.
**Rule:** Any pytest fixture in this repo that creates an SQLAlchemy session via `AsyncSessionLocal()` (or equivalent) must call `await engine.dispose()` after closing the session. Pytest-asyncio creates a new event loop per test by default, and asyncpg connections from a previous loop will fail with a confusing "different loop" error when the next test tries to use them. This is non-negotiable on Windows and likely flaky on Linux too.

---

## Don't ask permission to capture lessons — they're for me, not the user

**Date:** 2026-04-11
**Trigger:** After surfacing 3 candidate lessons during the Week 5 plan correction, I asked the user "Want me to capture those in lessons.md now, or just start Chunk 22?"
**Correction:** User: "Don't take permission from me while capturing any lessons, these lessons are for you to learn."
**Rule:** `tasks/lessons.md` is internal — it's the self-improvement loop from CLAUDE.md, not a user-facing artifact that needs sign-off. Whenever I notice a pattern worth capturing (user correction, latent bug I missed, process gap), append it to `lessons.md` immediately and silently. Don't surface "should I write this down?" as a question. The user only needs to know I captured something if it changes how the next chunk is going to run. Quietly updating lessons.md is part of normal work, not a checkpoint.

---

## Cross-check test counts in the strategy table against the detailed test lists

**Date:** 2026-04-11
**Trigger:** I drafted §18 (Week 5 plan) with Chunk 24 listed as "+20" in the strategy table at the top of the section, but the detailed test breakdown immediately below totaled to 24 tests. The cumulative-test-count table at the bottom used 24, the verification step said "20 green". User caught the inconsistency in their plan review: "Chunk 24 test count says +20 in the strategy table but +24 in the detailed test list. The cumulative math uses +24. Update the strategy table to match."
**Correction:** Numbers across sub-sections of the same plan must agree.
**Rule:** Before publishing any chunk plan, do a final pass that grep-greps the test count for each chunk across (1) the strategy table at the top, (2) the per-chunk Tests section, (3) the verification step, and (4) the cumulative test-count table at the bottom. All four must match. If I changed the test count anywhere mid-draft, propagate the change to all four locations *in the same edit*, not as a follow-up. Mismatched numbers are a credibility tax — the user has to mentally figure out which is right.

---

## Webhook-driven state machines: ask "what transitions happen *without* a webhook?"

**Date:** 2026-04-11
**Trigger:** §18 originally had `require_active_plan` checking only `team.plan == "cancelled"`. User caught the gap: "What happens when the 7-day trial expires and the user never paid? That's neither a cancellation (no subscription to cancel) nor an active plan." A user who signs up, never converts, and lets the trial expire would have NO Stripe event fire (no subscription = no `customer.subscription.deleted`), so the cancellation gate would never catch them and they'd write forever.
**Correction:** Added a second check inside `require_active_plan`: `team.trial_ends_at < now() AND team.stripe_customer_id IS NULL` → block writes with `limit_name="trial_expired"`. Computed live from existing columns, no background job needed.
**Rule:** When designing any state machine that's driven by external webhooks (Stripe, OAuth callbacks, QStash, etc.), explicitly enumerate every state transition and ask "does a webhook event fire for this transition?" If the answer is "no" for any transition, that state has to be **computed live from other state**, not waited on. Examples: trial expiry (no webhook), token expiry (no webhook — must compute from `expires_at`), file deletion garbage collection (no webhook). Whenever you see a `webhook_handler.dispatch(event_type)` design, immediately list the events that DON'T exist and figure out how each one is detected.

---

## Read all design decisions as a set after writing them, looking for contradictions

**Date:** 2026-04-11
**Trigger:** §18 Decision 2 said "Trial expiry is a soft signal: the middleware still gates against creator-tier limits, no hard cutoff." Decision 5 said "Cancellation is a HARD CUTOFF." The two decisions described two states (trial expiry, cancellation) with opposite enforcement behaviors — and I never noticed because I wrote each decision in isolation as I drafted the chunks. User caught it on plan review: "Decision 2 contradicts Decision 5." The fix required rewriting Decision 2 to match the hard-cutoff posture (and adding the trial-expired check to `require_active_plan`).
**Correction:** Decisions written in isolation can drift apart. The user had to do the consistency-checking I should have done before publishing.
**Rule:** After drafting a "Key design decisions" section, **read all the decisions as a single block** before publishing. For every pair of decisions that touch the same concept (e.g., cancellation + trial expiry both gate writes; mock-first storage + mock-first OAuth both gate the dev experience), explicitly ask "are these consistent?" If two decisions describe similar-shaped scenarios with different rules, that's almost always a bug — either one is wrong or they need to be merged into a single rule. The cost of catching this in plan review is one rewrite; the cost of catching it after Chunk 24 ships is rewriting the enforcement middleware AND backporting the fix into tests.

---

## Tests with UNIQUE columns must use unique IDs per test — never hardcode

**Date:** 2026-04-13
**Trigger:** Webhook tests in `test_billing_webhook.py` hardcoded `subscription_id="sub_test_123"` and `customer_id="cus_test_456"`. These passed in isolation but failed in the full suite because the `stripe_subscription_id` column has a UNIQUE constraint, and a prior test run had already inserted a team with `sub_test_123` into the shared local Postgres.
**Correction:** Self-corrected — replaced all hardcoded IDs with `_unique_ids()` helper that generates `sub_{uuid8}` / `cus_{uuid8}` per test invocation.
**Rule:** Any test that writes to a column with a UNIQUE constraint MUST generate a fresh unique value per invocation (UUID-based, timestamp-based, or `uuid.uuid4().hex[:8]`-based). Never hardcode IDs like `"sub_test_123"` — they work in isolation but collide across runs when the DB is shared. This applies to `stripe_subscription_id`, `stripe_customer_id`, `platform_video_id`, and any other UNIQUE column. Grep for `unique=True` in models before writing test helpers.

---

## `LIMIT N` without `ORDER BY` is a latent bug, not a style preference

**Date:** 2026-04-11
**Trigger:** `app/workers/discover_trends.py` had `LIMIT 100` with no `ORDER BY`. After enough test runs accumulated >100 active niches, brand-new test niches fell outside the limit (in DB-default order, which is undefined) and the test that asserted "create niche → run worker → niche has videos" started failing intermittently after Chunk 19 added more test runs. Hit me as 2 mysterious failures in the full-suite run.
**Correction:** Self-corrected — added `ORDER BY last_analyzed_at ASC NULLS FIRST, created_at ASC` so unprocessed niches always lead. Real production correctness improvement, not just a test fix.
**Rule:** Any `SELECT ... LIMIT N` query in this repo MUST have an explicit `ORDER BY` that gives deterministic + semantically-correct ordering. "It works for now because the table is small" is not a defense. For worker pickup queries specifically: order by staleness (NULLS FIRST for unprocessed rows, then oldest-processed) so newly-created rows can never be starved out by accumulated old ones.
