# FinBuddy Setup Guide — No API Key Required

This version uses pure JavaScript Code nodes. No Anthropic API,
no Claude AI Coach node, no credentials to configure.
The workflow responds in under 100ms with no external calls.

---

## What you need

- n8n Cloud account (n8n.cloud — free tier works)
- Claude account for claude.ai/design

---

## OPTION A — Import JSON (fastest, 2 minutes)

### Step 1 — Import the workflow

1. Log in to **app.n8n.cloud**
2. Click **Workflows** → **+ New Workflow**
3. Click the **⋮ menu** (top-right) → **Import from File**
4. Select `finbuddy_n8n_workflow.json`
5. Four nodes appear on the canvas:

```
[Webhook] → [Mock Credit Scorer] → [AI Response Generator] → [Respond to Webhook]
```

No sub-nodes. No credential prompts.

### Step 2 — Activate and copy webhook URL

1. Click the **Active** toggle (top-right) → it turns blue
2. Click the **Webhook** node
3. Copy the **Production URL**:
   ```
   https://YOUR-INSTANCE.app.n8n.cloud/webhook/finbuddy-check
   ```

### Step 3 — Test the webhook immediately

```bash
curl -s -X POST "https://YOUR-INSTANCE.app.n8n.cloud/webhook/finbuddy-check" \
  -H "Content-Type: application/json" \
  -d '{"persona_id":"rajesh","language":"hindi"}' | python3 -m json.tool
```

Expected: full JSON with `decision`, `approved_amount`, `shap_factors`, `roadmap`.

### Step 4 — Open Claude Design

1. Go to **claude.ai/design** → **+ New Design**
2. Paste the full contents of `finbuddy_claude_design_prompt.txt`
3. Press Enter — wait ~45 seconds

### Step 5 — Replace WEBHOOK_URL

In the Claude Design chat, send:
```
Replace WEBHOOK_URL with: https://YOUR-INSTANCE.app.n8n.cloud/webhook/finbuddy-check
```

Or open the code panel (< > icon), find `const WEBHOOK_URL = "WEBHOOK_URL";`
and replace the placeholder string.

### Step 6 — Share with judges

1. Click **Share** (top-right in Claude Design) → toggle ON
2. Copy the public link

---

## OPTION B — Build manually in n8n UI (n8n v2.17.5)

Use this if JSON import doesn't work.

### Step 1 — Create a new workflow

Open **app.n8n.cloud** → Workflows → **+ New Workflow**

---

### Step 2 — Add Webhook node

1. Click **+** on the canvas → search **Webhook** → select it
2. Set:
   - **HTTP Method**: POST
   - **Path**: `finbuddy-check`
   - **Response Mode**: `Respond Using Respond to Webhook Node`
   - **Allowed Origins (CORS)**: `*`
3. Click outside to close

---

### Step 3 — Add Mock Credit Scorer (Code node)

1. Click **+** after the Webhook node → search **Code** → select it
2. Rename node: `Mock Credit Scorer`
3. Set **Language** to **JavaScript**
4. Paste this code:

```javascript
const raw = $input.first().json;
const body = raw.body || raw;
const pid = ((body && body.persona_id) || 'rajesh').toLowerCase().trim();

const RAJESH = {
  persona_id: 'rajesh', name: 'Rajesh Kumar',
  role: 'Auto-rickshaw driver', city: 'Bengaluru',
  requested_amount: 20000, approved_amount: 18000,
  language: 'hindi', months_of_data: 6,
  income_signals: { avg_monthly: 20000, regularity_score: 0.82 },
  upi_patterns: { tx_count_30d: 400, merchant_diversity: 12,
    balance_dip_freq: 2, b2b_ratio: 0.15, months: 6 },
  confidence: { score: 78, data_quality: 'moderate',
    primary_signal: 'UPI income regularity' },
  shap_factors: [
    { factor: 'UPI income regularity', impact: 0.82, direction: 'positive',
      plain_english: 'Rs 18-22K hits your account every month.',
      action: 'Ensure income credits before 5th each month.' },
    { factor: 'No credit history', impact: -0.45, direction: 'negative',
      plain_english: 'Banks have no track record for you.',
      action: 'Take one FinBuddy micro-loan and repay on time.' },
    { factor: 'Merchant diversity', impact: 0.38, direction: 'positive',
      plain_english: '12 merchants shows steady business.',
      action: 'Keep transacting across Swiggy, petrol, groceries.' }
  ]
};

const MEENA = {
  persona_id: 'meena', name: 'Meena Devi',
  role: 'Kirana store owner', city: 'Chennai',
  requested_amount: 35000, approved_amount: 32000,
  language: 'english', months_of_data: 12,
  income_signals: { avg_monthly: 37000, regularity_score: 0.91 },
  upi_patterns: { tx_count_30d: 4500, merchant_diversity: 28,
    balance_dip_freq: 0, b2b_ratio: 0.65, months: 12 },
  confidence: { score: 91, data_quality: 'rich',
    primary_signal: 'B2B receipt volume' },
  shap_factors: [
    { factor: 'Daily transaction volume', impact: 0.89, direction: 'positive',
      plain_english: '150 daily transactions prove shop thriving.',
      action: 'Digitise payments via PhonePe or GPay.' },
    { factor: 'GST filing gaps', impact: -0.38, direction: 'negative',
      plain_english: 'Two missing GST months reduce confidence.',
      action: 'File GST monthly — zero-return months count.' },
    { factor: 'B2B receipt ratio', impact: 0.55, direction: 'positive',
      plain_english: '65% business income is very strong.',
      action: 'Request digital receipts from all suppliers.' }
  ]
};

return [{ json: ({ rajesh: RAJESH, meena: MEENA })[pid] || RAJESH }];
```

---

### Step 4 — Add AI Response Generator (Code node)

1. Click **+** after Mock Credit Scorer → **Code**
2. Rename: `AI Response Generator`
3. Language: JavaScript
4. Paste this code:

```javascript
const profile = $input.first().json;
const pid = (profile.persona_id || 'rajesh').toLowerCase();

const RAJESH_RESPONSE = {
  decision: 'conditional',
  approved_amount: 18000,
  confidence: { score: 78, data_quality: 'moderate',
    primary_signal: 'UPI income regularity' },
  shap_factors: [
    { factor: 'UPI income regularity', impact: 0.82, direction: 'positive',
      plain_english: 'Rs 18-22K hits your account every month.',
      action: 'Ensure income credits before 5th each month.' },
    { factor: 'No credit history', impact: -0.45, direction: 'negative',
      plain_english: 'Banks have no track record for you.',
      action: 'Take one FinBuddy micro-loan and repay on time.' },
    { factor: 'Merchant diversity', impact: 0.38, direction: 'positive',
      plain_english: '12 merchants shows steady business.',
      action: 'Keep transacting across Swiggy, petrol, groceries.' }
  ],
  roadmap: [
    { step: 1, milestone: 'Complete 60 deliveries',
      action: '2/day for 30 days on Swiggy Partner app.',
      unlock_amount: 20000, timeline_days: 30 },
    { step: 2, milestone: 'Repay this loan on time',
      action: 'Every repayment builds your credit footprint.',
      unlock_amount: 25000, timeline_days: 60 },
    { step: 3, milestone: 'Link bank statement',
      action: 'Share 3 months via Account Aggregator.',
      unlock_amount: 30000, timeline_days: 90 }
  ],
  vernacular_message: 'Rajesh bhai, aapko Rs 18,000 approved hai! Aapki mehnat rang laayi — UPI income har mahine regular aati hai. Aapka raasta khul raha hai.',
  minimum_offer: 2000
};

const MEENA_RESPONSE = {
  decision: 'approved',
  approved_amount: 32000,
  confidence: { score: 91, data_quality: 'rich',
    primary_signal: 'B2B receipt volume' },
  shap_factors: [
    { factor: 'Daily transaction volume', impact: 0.89, direction: 'positive',
      plain_english: '150 daily transactions prove your shop is thriving.',
      action: 'Digitise more payments via PhonePe or GPay.' },
    { factor: 'GST filing gaps', impact: -0.38, direction: 'negative',
      plain_english: 'Two missing GST months reduce lender confidence.',
      action: 'File GST monthly — zero-return months still count.' },
    { factor: 'B2B receipt ratio', impact: 0.55, direction: 'positive',
      plain_english: '65% business income is very strong.',
      action: 'Request digital receipts from all suppliers.' }
  ],
  roadmap: [
    { step: 1, milestone: 'File missing GST returns',
      action: 'Complete both months at gst.gov.in.',
      unlock_amount: 35000, timeline_days: 15 },
    { step: 2, milestone: 'Digitise supplier receipts',
      action: 'Link all supplier payments to business UPI.',
      unlock_amount: 40000, timeline_days: 30 },
    { step: 3, milestone: 'Link business bank account',
      action: 'Share 3 months via Account Aggregator.',
      unlock_amount: 50000, timeline_days: 45 }
  ],
  vernacular_message: 'Meena ji, Rs 32,000 approved for your inventory! Your B2B volume and daily transactions show a thriving business. File those two GST returns and your next limit goes to Rs 40,000.',
  minimum_offer: 2000
};

const result = ({ rajesh: RAJESH_RESPONSE, meena: MEENA_RESPONSE })[pid] || RAJESH_RESPONSE;
return [{ json: result }];
```

---

### Step 5 — Add Respond to Webhook node

1. Click **+** after AI Response Generator → search **Respond to Webhook**
2. Set:
   - **Respond With**: `Using JSON`
   - **Response Body**: `={{ $json }}`
3. Click **Add Header** twice:
   - Header 1: Name `Access-Control-Allow-Origin` | Value `*`
   - Header 2: Name `Content-Type` | Value `application/json`

---

### Step 6 — Connect the nodes

Verify connections (drag from output dot to input dot if missing):
```
Webhook → Mock Credit Scorer → AI Response Generator → Respond to Webhook
```

---

### Step 7 — Save and test

1. Press **Ctrl+S** to save
2. Click **Execute Workflow** (▶ button, top-right)
3. Click the **Webhook** node → copy the **Test URL**
4. In a terminal:
   ```bash
   curl -s -X POST "https://YOUR-INSTANCE.app.n8n.cloud/webhook-test/finbuddy-check" \
     -H "Content-Type: application/json" \
     -d '{"persona_id":"rajesh","language":"hindi"}'
   ```
5. You should see the full FinBuddy JSON in the response

> For production: toggle **Active** ON → use the **Production URL** (no `-test` in path)

---

### Steps 8–10 — Claude Design (same as Option A above)

Follow Option A Steps 4–6.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| HTTP 404 | Workflow not active | Toggle Active ON (production) or click Execute Workflow (test) |
| HTTP 200, empty body | Respond to Webhook misconfigured | Set Respond With = JSON, Response Body = `={{ $json }}` |
| Response arrives instantly but wrong shape | AI Response Generator returning error | Check Code node syntax — paste code fresh from Step 4 above |
| CORS error in browser | Workflow not active | Toggle Active ON |
| "Fallback Model" error | Anthropic node accidentally added | Delete it — this workflow needs no Anthropic nodes |

---

## Architecture

```
Browser POST {"persona_id":"rajesh","language":"hindi"}
       ↓
n8n Webhook  — receives POST body
       ↓
Mock Credit Scorer (Code)
  Reads persona_id → returns full profile object
       ↓
AI Response Generator (Code)
  Reads profile.persona_id
  Returns hardcoded FinBuddy JSON (decision, amount,
  SHAP factors, roadmap, vernacular message)
  No external calls. Runs in < 5ms.
       ↓
Respond to Webhook
  Returns $json directly as response body
  Access-Control-Allow-Origin: *
       ↓
Browser renders Screen 2 (results)
```

**No API keys. No credentials. No billing. Works immediately.**
