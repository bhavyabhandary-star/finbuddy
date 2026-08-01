#!/usr/bin/env bash
# FinBuddy End-to-End Test Script
# Usage:   ./finbuddy_test.sh <N8N_WEBHOOK_URL>
# Example: ./finbuddy_test.sh https://bhavyabhandary.app.n8n.cloud/webhook/finbuddy-check

set -euo pipefail

GREEN="\033[0;32m"; RED="\033[0;31m"; YELLOW="\033[1;33m"
CYAN="\033[0;36m";  BOLD="\033[1m";   RESET="\033[0m"

TOTAL_PASS=0; TOTAL_FAIL=0

pass() { echo -e "  ${GREEN}✓ PASS${RESET}  $1"; TOTAL_PASS=$((TOTAL_PASS+1)); }
fail() { echo -e "  ${RED}✗ FAIL${RESET}  $1"; TOTAL_FAIL=$((TOTAL_FAIL+1)); }
section() { echo -e "\n${BOLD}${YELLOW}━━━ $1 ━━━${RESET}"; }

# ─── arg check ──────────────────────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
  echo -e "${RED}Usage:${RESET} $0 <N8N_WEBHOOK_URL>"
  echo "Example: $0 https://bhavyabhandary.app.n8n.cloud/webhook/finbuddy-check"
  exit 1
fi
N8N_URL="${1%/}"

echo -e "\n${BOLD}FinBuddy Integration Tests${RESET}"
echo -e "Webhook: ${CYAN}${N8N_URL}${RESET}\n"

# ─── helpers ────────────────────────────────────────────────────────────────
post_webhook() {
  local payload="$1"
  local tmp; tmp=$(mktemp)
  local code
  code=$(curl -s -o "$tmp" -w "%{http_code}" \
    --max-time 60 -X POST "$N8N_URL" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>/dev/null)
  local body; body=$(cat "$tmp"); rm -f "$tmp"

  # Unwrap n8n text wrapper: {"text":"...json..."} → inner JSON
  if echo "$body" | grep -q '"text"' && ! echo "$body" | grep -q '"decision"'; then
    local inner
    inner=$(echo "$body" | sed 's/.*"text":"\(.*\)".*/\1/' \
      | sed 's/\\n//g;s/\\"/"/g;s/\\t//g' \
      | grep -o '{.*}' | head -1)
    [[ -n "$inner" ]] && body="$inner"
  fi

  echo "${code}|||${body}"
}

check_field() {
  local body="$1" field="$2"
  if echo "$body" | grep -q "\"$field\""; then
    pass "field present: $field"
  else
    fail "field missing: $field"
  fi
}

# ─── CHECK 1 — Rajesh ───────────────────────────────────────────────────────
section "CHECK 1  Rajesh Kumar (Hindi, gig worker)"
echo -e "  ${CYAN}POST${RESET} {persona_id:rajesh, language:hindi} ..."

R_PAYLOAD='{"persona_id":"rajesh","requested_amount":20000,"language":"hindi","income_signals":{"avg_monthly":20000,"regularity_score":0.82},"upi_patterns":{"tx_count_30d":400,"merchant_diversity":12,"balance_dip_freq":2,"b2b_ratio":0.15},"months_of_data":6}'
R_RESULT=$(post_webhook "$R_PAYLOAD")
R_CODE=$(echo "$R_RESULT" | cut -d'|' -f1)
R_BODY=$(echo "$R_RESULT" | sed 's/^[0-9]*|||//')

if [[ "$R_CODE" == "200" ]]; then
  pass "HTTP 200"
else
  fail "HTTP $R_CODE (expected 200) — is the workflow active?"
fi

if [[ -z "$R_BODY" || "$R_BODY" == "null" || "$R_BODY" == "{}" ]]; then
  fail "Response body is empty — Anthropic credential not linked to Claude Sonnet Model node"
else
  for f in decision approved_amount confidence shap_factors roadmap vernacular_message minimum_offer; do
    check_field "$R_BODY" "$f"
  done

  # decision value
  R_DEC=$(echo "$R_BODY" | grep -o '"decision":"[^"]*"' | head -1 | sed 's/"decision":"//;s/"//')
  if [[ "$R_DEC" == "approved" || "$R_DEC" == "conditional" || "$R_DEC" == "declined" ]]; then
    pass "decision valid: \"$R_DEC\""
  else
    fail "decision invalid: \"$R_DEC\""
  fi

  # approved_amount
  R_AMT=$(echo "$R_BODY" | grep -o '"approved_amount":[0-9]*' | head -1 | grep -o '[0-9]*$')
  if [[ -n "$R_AMT" && "$R_AMT" -gt 0 ]]; then
    pass "approved_amount: Rs $R_AMT"
  else
    fail "approved_amount missing or zero"
  fi

  # shap_factors count
  R_SHAP=$(echo "$R_BODY" | grep -o '"factor"' | wc -l | tr -d ' ')
  if [[ "$R_SHAP" -ge 2 ]]; then
    pass "shap_factors: $R_SHAP items (>= 2)"
    echo "$R_BODY" | grep -q '"plain_english"' && pass "plain_english present" || fail "plain_english missing"
    echo "$R_BODY" | grep -q '"action"'        && pass "action present"        || fail "action missing"
    echo "$R_BODY" | grep -q '"direction"'     && pass "direction present"     || fail "direction missing"
  else
    fail "shap_factors: only $R_SHAP item(s), need >= 2"
  fi

  # roadmap steps
  R_STEPS=$(echo "$R_BODY" | grep -o '"step"' | wc -l | tr -d ' ')
  if [[ "$R_STEPS" -eq 3 ]]; then
    pass "roadmap: exactly 3 steps"
  else
    fail "roadmap: $R_STEPS step(s), expected 3"
  fi

  # minimum_offer
  R_MIN=$(echo "$R_BODY" | grep -o '"minimum_offer":[0-9]*' | head -1 | grep -o '[0-9]*$')
  if [[ -n "$R_MIN" && "$R_MIN" -ge 2000 ]]; then
    pass "minimum_offer >= Rs 2,000 (Rs $R_MIN)"
  else
    fail "minimum_offer must be >= 2000, got: \"$R_MIN\""
  fi

  # Hindi language check
  if echo "$R_BODY" | grep -qiE '(aap|hai|raasta|mehnat|kadam|taakat)'; then
    pass "vernacular_message appears Hindi"
  else
    fail "vernacular_message does not look Hindi (check language routing)"
  fi

  # Bias guard
  BIAS_OK=true
  for w in rejected denied failed ineligible CIBIL caste; do
    if echo "$R_BODY" | grep -iq "$w"; then
      fail "Bias violation: banned word \"$w\" in response"
      BIAS_OK=false
    fi
  done
  $BIAS_OK && pass "Bias guard: no banned words"
fi

# ─── CHECK 2 — Meena ────────────────────────────────────────────────────────
section "CHECK 2  Meena Devi (English, kirana owner)"
echo -e "  ${CYAN}POST${RESET} {persona_id:meena, language:english} ..."

M_PAYLOAD='{"persona_id":"meena","requested_amount":35000,"language":"english","income_signals":{"avg_monthly":37000,"regularity_score":0.91},"upi_patterns":{"tx_count_30d":4500,"merchant_diversity":28,"balance_dip_freq":0,"b2b_ratio":0.65},"months_of_data":12}'
M_RESULT=$(post_webhook "$M_PAYLOAD")
M_CODE=$(echo "$M_RESULT" | cut -d'|' -f1)
M_BODY=$(echo "$M_RESULT" | sed 's/^[0-9]*|||//')

if [[ "$M_CODE" == "200" ]]; then
  pass "HTTP 200"
else
  fail "HTTP $M_CODE (expected 200)"
fi

if [[ -z "$M_BODY" || "$M_BODY" == "null" ]]; then
  fail "Response body empty — Anthropic credential not linked"
else
  for f in decision approved_amount shap_factors roadmap vernacular_message; do
    check_field "$M_BODY" "$f"
  done

  M_AMT=$(echo "$M_BODY" | grep -o '"approved_amount":[0-9]*' | head -1 | grep -o '[0-9]*$')
  if [[ -n "$M_AMT" && "$M_AMT" -gt 0 ]]; then
    pass "approved_amount: Rs $M_AMT"
  else
    fail "approved_amount missing or zero"
  fi

  M_STEPS=$(echo "$M_BODY" | grep -o '"step"' | wc -l | tr -d ' ')
  [[ "$M_STEPS" -eq 3 ]] && pass "roadmap: exactly 3 steps" || fail "roadmap: $M_STEPS steps (expected 3)"

  # amounts differ
  if [[ -n "${R_AMT:-}" && -n "$M_AMT" && "$R_AMT" != "$M_AMT" ]]; then
    pass "Rajesh Rs $R_AMT ≠ Meena Rs $M_AMT (personas return different amounts)"
  else
    fail "Both personas returned same approved_amount — check mock scorer"
  fi

  BIAS_OK=true
  for w in rejected denied failed ineligible; do
    if echo "$M_BODY" | grep -iq "$w"; then
      fail "Bias violation: \"$w\" in Meena response"; BIAS_OK=false; fi
  done
  $BIAS_OK && pass "Bias guard: no banned words"
fi

# ─── CHECK 3 — CORS ─────────────────────────────────────────────────────────
section "CHECK 3  CORS headers"
CORS_HEADERS=$(curl -s -I -X POST "$N8N_URL" \
  -H "Content-Type: application/json" \
  -d '{"persona_id":"rajesh","language":"hindi"}' \
  --max-time 60 2>/dev/null || true)

echo "$CORS_HEADERS" | grep -iq "access-control-allow-origin" \
  && pass "Access-Control-Allow-Origin present" \
  || fail "Access-Control-Allow-Origin missing (browser fetch will be blocked)"

# ─── SUMMARY ────────────────────────────────────────────────────────────────
TOTAL=$((TOTAL_PASS + TOTAL_FAIL))
echo ""
echo "$(printf '═%.0s' {1..58})"
if [[ $TOTAL_FAIL -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}  ALL $TOTAL CHECKS PASSED${RESET} — FinBuddy stack is live and healthy."
else
  echo -e "${RED}${BOLD}  $TOTAL_FAIL of $TOTAL checks FAILED${RESET} — see output above."
  echo ""
  echo "  Most common fixes:"
  echo "  • Empty body  → link Anthropic credential to Claude Sonnet Model node"
  echo "  • HTTP 404    → toggle workflow Active switch ON in n8n editor"
  echo "  • CORS miss   → activate the workflow (CORS headers only send when active)"
fi
echo "$(printf '═%.0s' {1..58})"
echo ""

exit "$TOTAL_FAIL"
