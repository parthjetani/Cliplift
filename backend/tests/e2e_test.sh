#!/usr/bin/env bash
# End-to-end API test suite using real Supabase tokens.
# Run this with the FastAPI server running on :8000 and Supabase on :54321.

set -u
SUPABASE_URL="http://127.0.0.1:54321"
ANON_KEY="sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"
API="http://127.0.0.1:8000"
EMAIL="test+$(date +%s)@cliplift.com"
PASSWORD="TestPassword123!"

FAILED=0
pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; FAILED=1; }

# assert_json BODY DOTPATH EXPECTED DESC
assert_json() {
  local body="$1" path="$2" expected="$3" desc="$4"
  local actual
  actual=$(echo "$body" | python -c "
import sys, json
d = json.load(sys.stdin)
for p in '$path'.split('.'):
    if isinstance(d, dict) and p in d:
        d = d[p]
    else:
        d = None
        break
print(d if d is not None else 'None')
" 2>/dev/null)
  if [ "$actual" = "$expected" ]; then
    pass "$desc"
  else
    fail "$desc (got: '$actual', expected: '$expected')"
  fi
}

echo "============================================"
echo "  CLIPLIFT API E2E TEST SUITE"
echo "============================================"
echo

# ----------------------------------------------------------------------------
echo "── TEST 1: Health endpoint ──"
RESP=$(curl -s -w "\n%{http_code}" "$API/health")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)
[ "$CODE" = "200" ] && pass "GET /health → 200" || fail "Got $CODE"
assert_json "$BODY" "status" "ok" "status = ok"
assert_json "$BODY" "environment" "development" "environment = development"
echo

# ----------------------------------------------------------------------------
echo "── TEST 2: Root endpoint ──"
RESP=$(curl -s -w "\n%{http_code}" "$API/")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)
[ "$CODE" = "200" ] && pass "GET / → 200" || fail "Got $CODE"
assert_json "$BODY" "name" "Cliplift" "name = Cliplift"
echo

# ----------------------------------------------------------------------------
echo "── TEST 3: Auth required for protected endpoints ──"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/v1/profile")
[ "$CODE" = "401" ] && pass "GET /profile (no auth) → 401" || fail "Got $CODE"

CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/v1/profile" -H "Authorization: Bearer not.a.real.jwt")
[ "$CODE" = "401" ] && pass "Bogus Bearer → 401" || fail "Got $CODE"

CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/v1/profile" -H "Authorization: NotBearer xyz")
[ "$CODE" = "401" ] && pass "Malformed Authorization header → 401" || fail "Got $CODE"
echo

# ----------------------------------------------------------------------------
echo "── TEST 4: Sign up real user via Supabase ──"
echo "  Email: $EMAIL"
SIGNUP=$(curl -s -X POST "$SUPABASE_URL/auth/v1/signup" \
  -H "apikey: $ANON_KEY" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
TOKEN=$(echo "$SIGNUP" | python -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")
USER_ID=$(echo "$SIGNUP" | python -c "import sys, json; print(json.load(sys.stdin).get('user', {}).get('id', ''))")
[ -n "$TOKEN" ] && pass "Got access_token" || { fail "No token: $SIGNUP"; exit 1; }
[ -n "$USER_ID" ] && pass "User ID: $USER_ID" || fail "No user ID"
echo

# ----------------------------------------------------------------------------
echo "── TEST 5: GET /api/v1/profile with REAL ES256 token ──"
RESP=$(curl -s -w "\n%{http_code}" "$API/api/v1/profile" -H "Authorization: Bearer $TOKEN")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)
[ "$CODE" = "200" ] && pass "GET /profile → 200" || fail "Got $CODE: $BODY"
assert_json "$BODY" "id" "$USER_ID" "Profile.id matches auth.users.id"
assert_json "$BODY" "email" "$EMAIL" "Profile.email matches"
echo

# ----------------------------------------------------------------------------
echo "── TEST 6: Trigger created profile row in DB ──"
COUNT=$(docker exec supabase_db_Virlo.ai psql -U postgres -tA -c "SELECT count(*) FROM public.profiles WHERE id = '$USER_ID'" 2>/dev/null)
[ "$COUNT" = "1" ] && pass "profiles row exists (trigger fired)" || fail "Trigger did not fire (count=$COUNT)"
echo

# ----------------------------------------------------------------------------
echo "── TEST 7: PUT /api/v1/profile (full update) ──"
RESP=$(curl -s -w "\n%{http_code}" -X PUT "$API/api/v1/profile" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","avatar_url":"https://example.com/avatar.png"}')
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)
[ "$CODE" = "200" ] && pass "PUT /profile → 200" || fail "Got $CODE"
assert_json "$BODY" "name" "Test User" "Name updated to 'Test User'"
assert_json "$BODY" "avatar_url" "https://example.com/avatar.png" "Avatar URL updated"
assert_json "$BODY" "id" "$USER_ID" "ID unchanged"
echo

# ----------------------------------------------------------------------------
echo "── TEST 8: Update persisted across requests ──"
BODY=$(curl -s "$API/api/v1/profile" -H "Authorization: Bearer $TOKEN")
assert_json "$BODY" "name" "Test User" "Name persisted"
assert_json "$BODY" "avatar_url" "https://example.com/avatar.png" "Avatar persisted"
echo

# ----------------------------------------------------------------------------
echo "── TEST 9: PUT with partial update ──"
RESP=$(curl -s -w "\n%{http_code}" -X PUT "$API/api/v1/profile" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Updated Name"}')
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)
[ "$CODE" = "200" ] && pass "Partial PUT → 200" || fail "Got $CODE"
assert_json "$BODY" "name" "Updated Name" "Name updated"
assert_json "$BODY" "avatar_url" "https://example.com/avatar.png" "Avatar preserved (partial update)"
echo

# ----------------------------------------------------------------------------
echo "── TEST 10: Validation error → 422 ──"
LONG_NAME=$(python -c "print('x' * 300)")
RESP=$(curl -s -w "\n%{http_code}" -X PUT "$API/api/v1/profile" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$LONG_NAME\"}")
CODE=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | head -n -1)
[ "$CODE" = "422" ] && pass "Long name → 422" || fail "Got $CODE"
assert_json "$BODY" "error.code" "validation_error" "Error code = validation_error"
echo

# ----------------------------------------------------------------------------
echo "── TEST 11: User isolation ──"
EMAIL2="test+$(($(date +%s) + 10))@cliplift.com"
SIGNUP2=$(curl -s -X POST "$SUPABASE_URL/auth/v1/signup" \
  -H "apikey: $ANON_KEY" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL2\",\"password\":\"$PASSWORD\"}")
TOKEN2=$(echo "$SIGNUP2" | python -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")
USER_ID2=$(echo "$SIGNUP2" | python -c "import sys, json; print(json.load(sys.stdin).get('user', {}).get('id', ''))")

BODY=$(curl -s "$API/api/v1/profile" -H "Authorization: Bearer $TOKEN2")
assert_json "$BODY" "id" "$USER_ID2" "User 2 sees own ID"
assert_json "$BODY" "email" "$EMAIL2" "User 2 sees own email"
assert_json "$BODY" "name" "None" "User 2 has no name (no leak from user 1)"

BODY=$(curl -s "$API/api/v1/profile" -H "Authorization: Bearer $TOKEN")
assert_json "$BODY" "id" "$USER_ID" "User 1 token still returns user 1"
assert_json "$BODY" "name" "Updated Name" "User 1 still has Updated Name"
echo

# ----------------------------------------------------------------------------
echo "── TEST 12: Login (signInWithPassword) issues fresh token ──"
LOGIN=$(curl -s -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
  -H "apikey: $ANON_KEY" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
LOGIN_TOKEN=$(echo "$LOGIN" | python -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")
[ -n "$LOGIN_TOKEN" ] && pass "Login returned fresh access_token" || fail "Login failed"

BODY=$(curl -s "$API/api/v1/profile" -H "Authorization: Bearer $LOGIN_TOKEN")
assert_json "$BODY" "id" "$USER_ID" "Login token works on /profile"
echo

# ----------------------------------------------------------------------------
echo "── TEST 13: OpenAPI + Docs reachable ──"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/openapi.json")
[ "$CODE" = "200" ] && pass "GET /openapi.json → 200" || fail "Got $CODE"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/docs")
[ "$CODE" = "200" ] && pass "GET /docs → 200" || fail "Got $CODE"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/redoc")
[ "$CODE" = "200" ] && pass "GET /redoc → 200" || fail "Got $CODE"
echo

# ----------------------------------------------------------------------------
echo "── TEST 14: CORS preflight ──"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X OPTIONS "$API/api/v1/profile" \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization")
[ "$CODE" = "200" ] && pass "CORS preflight → 200" || fail "Got $CODE"
echo

echo "============================================"
if [ "$FAILED" = "0" ]; then
  echo "  ✅ ALL TESTS PASSED"
else
  echo "  ❌ FAILED TESTS DETECTED"
  exit 1
fi
echo "============================================"
