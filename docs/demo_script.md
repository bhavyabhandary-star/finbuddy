# FinBuddy Demo Script

~5-6 minutes. Every command and number below is real -- pulled from actual runs in
this repo, not scripted-sounding placeholders. URLs below point at the live deployed
Spaces (verified working end to end); swap for `http://localhost:8001` /
`http://localhost:8002` if demoing from a local `uvicorn` run instead.

**Record a backup video of this exact run before the live demo**, in case wifi/API
rate limits/Space cold-starts cause trouble live.

## 1. Open with the problem (30s)

"Gig workers don't have a traditional credit history -- FinBuddy scores them from UPI
transaction signals instead, via consent-based Account Aggregator data. Because this
feeds real lending decisions, RBI's Digital Lending Directions and DPDP Act apply
directly -- we treated compliance as a functional requirement throughout, not
polish. I'll show four things: a real scoring call, a real RAG-grounded compliance
answer with citations, a real WhatsApp exchange through Twilio, and the governance
gates that would block a bad model from shipping."

## 2. Live scoring call (60s)

```bash
curl -X POST https://bhavyabhandary-finbuddy-scoring.hf.space/api/v1/score -H "Content-Type: application/json" -d '{
  "avg_monthly_income": 21000,
  "income_regularity_score": 0.81,
  "tx_count_30d": 340,
  "merchant_diversity": 11,
  "balance_dip_frequency": 3,
  "b2b_ratio": 0.12,
  "avg_transaction_size": 95,
  "tenure_months": 6,
  "geography": "rural"
}'
```

Point out live, on screen:
- `credit_score` and `calibrated_probability_of_repayment` -- a real calibrated PD,
  not a raw model score.
- `top_3_factors` -- plain-language, computed via XGBoost's native Tree SHAP
  (mention: no `shap` package needed, avoided a blocked-DLL issue on the dev
  machine by using the same underlying algorithm through a different implementation).
- `fairness_mitigation_applied: true` -- this specific decision went through the
  F-012 fairness-mitigated threshold, not a plain probability cutoff, because
  `geography` was supplied.
- `latency_ms` -- real number, typically ~90-130ms, well under the 500ms budget.

## 3. Live RAG-grounded compliance answer (90s)

```bash
curl -X POST https://bhavyabhandary-finbuddy-rag-coach.hf.space/api/v1/whatsapp-coach/respond -H "Content-Type: application/json" -d '{
  "user_query": "why do you need my UPI data",
  "f001_credit_score": 720,
  "f003_shap_top_3": ["income_regularity_score: +", "balance_dip_frequency: -"]
}'
```

Point out:
- `sources` -- every answer cites the exact corpus chunk(s) it's grounded in, with
  similarity scores, for auditability.
- Say explicitly: "if I ask something off-topic, it won't guess." Then run:

```bash
curl -X POST https://bhavyabhandary-finbuddy-rag-coach.hf.space/api/v1/whatsapp-coach/respond -H "Content-Type: application/json" -d '{
  "user_query": "what is the weather like today"
}'
```

Point out `escalate_to_human: true` firing correctly instead of a hallucinated answer.

**If time allows**, the strongest single moment in this whole build: ask about data
retention.

```bash
curl -X POST https://bhavyabhandary-finbuddy-rag-coach.hf.space/api/v1/whatsapp-coach/respond -H "Content-Type: application/json" -d '{
  "user_query": "how long do you keep my KYC and financial records"
}'
```

Explain: "An earlier draft of our compliance material stated this as a firm 7-year
figure -- that number actually belongs to a different obligation (Consent Manager
consent-record retention), not KYC/financial data, which is governed separately by
RBI/PMLA and hasn't been confirmed yet. The system won't repeat that conflation --
it says so, and we have a test (`tests/test_rag_pipeline.py`) that runs against the
real live model, not a mock, to prove it."

## 3b. Real WhatsApp message, live (45s)

If your phone is joined to the Twilio Sandbox, send an actual WhatsApp message to
the sandbox number on screen -- e.g. "Why do you need my UPI transaction data?" --
and show the real reply arriving. This is the same retrieval+Groq pipeline as step 3,
now proven over the actual channel judges will picture FinBuddy running on, not just
curl.

If wifi/phone access is unreliable during judging, use this real, already-verified
exchange as a screenshot backup instead (from Twilio's own message log, not staged):

```
[10:52:52] inbound  "Why do you need my UPI transaction data?"
[10:53:01] outbound "We need your UPI transaction data to understand your income
                      story..." (status: read)

[10:55:34] inbound  "What stock should I invest in this week?"
[10:55:36] outbound "I don't have a confident, verified answer to that from
                      FinBuddy's policy and coaching material. Let me connect you
                      with a human coach who can help directly." (status: read)
```

The second exchange is worth calling out explicitly: it proves the confidence gate
AND the no-financial-advice guardrail in one real message, and replies faster (2s vs
9s) because it skips the LLM call entirely when escalating.

## 4. Drift monitoring (45s)

```bash
python -m scoring_service.monitoring.drift_report
```

Show the three scenarios: `no_drift_control` (GREEN), `moderate_drift_amber` (AMBER,
PSI 0.116), `severe_drift_red` (RED, PSI 0.736) -- open one of the generated HTML
files (`scoring_service/monitoring/reports/`). Mention: implemented PSI+CUSUM
directly rather than via the `evidently` package, because evidently's pyarrow
dependency hit the same Windows DLL restriction that affected `shap` -- same honesty
pattern as the rest of the build, not hidden.

## 5. Governance gate summary (60s)

```bash
pytest tests/ -v
```

"26 passed, 2 skipped -- and the 2 skips are not swept under the rug." Point at:

```
tests/test_mlops_gates.py::test_f012_equalized_odds_requires_human_signoff[geography] SKIPPED (requires_human_signoff: ...)
```

"Geography and income_band have genuinely different true repayment rates in this
data -- rural 19%, urban 68%. When base rates differ that much, it's mathematically
provable you can't drive both demographic parity AND equalized odds to zero at once.
We prioritized demographic parity, the standard fair-lending criterion, and flagged
the resulting equalized-odds gap as a Risk & Compliance policy decision instead of
quietly picking a side. That's what CI actually blocks or doesn't block on."

## 6. Close (30s)

"Everything shown just now was a real API call against a real trained model, a real
Postgres+pgvector database, a real Groq model, and a real WhatsApp message through
Twilio -- not slides. We also ran the full Setu Account Aggregator flow live end to
end: real consent, real human approval, real mock bank data, real score. What's
still open: Legal sign-off on the policy corpus, Risk & Compliance sign-off on that
fairness trade-off, formal FIU licensing before this could touch a real user's real
consent, and retraining on real (not sandbox mock) Setu AA data before any real
lending decision relies on it. All flagged explicitly in the README and the code
itself, not glossed over."

## Backup plan if live calls fail during judging

1. Have the recorded backup video ready to play instead.
2. Fall back to `pytest tests/ -v` output (screenshot or terminal) plus the
   `scoring_service/monitoring/reports/*.html` files already generated -- these don't
   need network access once generated.
3. If only the RAG service is down (Groq rate limit, Neon cold start), the scoring
   service demo (step 2) still stands alone.
