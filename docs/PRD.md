# FinBuddy — Product Requirements Document

**Status:** Capstone / hackathon build, production-track architecture.
**Last updated:** 2026-08-02
**Owner:** Bhavya Bhandary

This PRD states what FinBuddy is required to do and why. For proof of what's
actually been built and verified against those requirements, see the root
[README.md](../README.md) (real numbers, real live endpoints) and
[demo_script.md](demo_script.md) (walkthrough). This document does not repeat
that evidence in full — it links to it where relevant.

## 1. Problem

Gig-economy workers in India (delivery riders, drivers, freelance platform
workers) are frequently thin-file or no-file for traditional credit scoring:
no salary slips, no consistent bank statement pattern an NBFC's legacy
underwriting model expects. They do, however, generate a rich, high-frequency
UPI transaction history through their platform earnings and daily spending.
That data exists; it's just never been used for credit access.

Two consequences of solving this the naive way, both unacceptable:
- Scoring gig workers without explaining *why* they were declined excludes
  people who could act on that explanation (pay down a balance-dip, get a
  second income source verified) — hence F-003 (explainability) is not
  optional polish, it's a requirement.
- Building an income-proxy model without checking it for geography/gender/
  income-band bias risks encoding exactly the exclusion this product exists
  to fix — hence F-012 (fairness audit) is not optional polish either.

## 2. Users

- **Primary: gig-economy borrower.** Wants a fast, explainable credit
  decision and ongoing plain-language coaching (why was my limit reduced,
  why do you need my data, how do I improve my score) without needing to
  read a policy document. Primary channel: WhatsApp (already installed,
  already trusted, no new app to download).
- **Secondary: NBFC lending partner.** Consumes the credit score, PD, and
  explanation via API to make a lending decision. Needs the decision to be
  auditable (source-cited, SHAP-explained) and compliant with RBI's Digital
  Lending Directions.
- **Internal: Risk & Compliance, Legal, MLOps.** Own the governance gates
  (Section 6) that must pass before any model output can be relied on for a
  real lending decision.

## 3. Regulatory context (functional requirement, not a checkbox)

- **RBI Digital Lending Directions, 2025** — governs disclosure to the
  borrower (why this decision, what data was used), fund routing, and the
  default loss guarantee cap on the lending arrangement. See
  `rag_service/finbuddy_rag_corpus/policy/rbi_*.md`.
- **DPDP Act & Rules, 2025** — governs consent (purpose-limited, revocable),
  data localization, and retention. Every UPI-data pull in this product goes
  through Setu's Account Aggregator consent flow with purpose code 103
  ("Bank statement verification or loan underwriting") — never a raw scrape
  or a pre-checked consent box. See
  `rag_service/finbuddy_rag_corpus/policy/dpdp_*.md`.

The WhatsApp coach exists specifically so a borrower can ask *why* a
decision was made or *why* their data is needed and get a real,
policy-grounded answer — not a generic chatbot, and never a guess dressed
up as a citation (Section 5.3).

## 4. Feature requirements

| ID | Feature | Requirement |
|---|---|---|
| F-001 | Credit Scoring | Score a borrower's repayment probability from 8 UPI-derived signals (income, regularity, transaction count, merchant diversity, balance-dip frequency, B2B ratio, avg transaction size, tenure). Target AUC ≥0.82. |
| F-003 | Explainability | Every score returns the top-3 contributing factors in plain language, not raw feature names or SHAP values a borrower can't read. Target latency <500ms. |
| — | Risk-Trend classifier | A lighter, faster model for periodic (monthly) portfolio-level risk re-scoring, independent of the real-time F-001 path. Target ROC-AUC ≥0.96. |
| F-006 | Anomaly Detection | Flag UPI patterns that look unlike the training distribution *before* scoring, so an anomalous profile is scored with an explicit lower-confidence flag rather than silently trusted. |
| F-007/9 | Voice & Intent | Accept a voice note (Hindi/Tamil/English) as an alternative to typing, transcribe it, and classify intent (loan_status, why_data_needed, limit_reduced, repayment_help, general_query) to route it correctly. |
| F-012 | Bias Audit | Audit F-001 for demographic parity, equalized odds, and disparate impact across gender, geography, and income band — each reported separately, not one aggregate "fairness score." Thresholds: DPD ≤0.05, DIR ≥0.80, EOD ≤0.05 where achievable (see Section 6 on the geography/income_band exception). |
| — | RAG Coach | Answer borrower questions about their score, FinBuddy's data practices, and RBI/DPDP policy using ONLY retrieved, cited corpus content — never unsupported model knowledge. Escalate to a human coach below a similarity-confidence threshold rather than guess. |
| — | WhatsApp delivery | The RAG Coach must be reachable over real WhatsApp (not just an internal API), since that's the channel borrowers actually have. |
| — | Setu AA integration | Fetch UPI signals via a real, consent-gated Account Aggregator pull (Setu), not a synthetic proxy, before any live lending decision. |

## 5. Architecture requirements

### 5.1 Serving modes

Three independent serving paths, since they have different latency/freshness
needs and shouldn't share a failure mode:

1. **Real-time** — F-006 anomaly pre-check → F-001 score + calibration →
   F-003 top-3 factors → fairness-aware approval decision. Budget: <500ms
   p95, end to end.
2. **Batch** — nightly re-scoring of the existing portfolio, for lenders who
   want periodic risk refresh without a live call per borrower.
3. **Champion/challenger** — a documented routing + metrics-comparison
   mechanism for safely rolling out a retrained model against a fraction of
   traffic before full cutover.

### 5.2 Data flow

```
Setu AA consent (purpose 103) -> 12-month UPI pull -> normalize to 8 signals
  -> F-006 anomaly check -> F-001 score + F-003 explanation
  -> NBFC lender API / React PWA dashboard / WhatsApp coach (RAG-grounded)
```

### 5.3 RAG retrieval requirements

- Corpus chunked paragraph/header-aware with 10-15% overlap — never fixed
  character-count splitting, which fragments policy statements mid-sentence.
- Retrieval below a 0.70 cosine-similarity confidence threshold MUST
  escalate to a human coach, never generate an answer anyway.
- Every generated answer returns its source chunk(s) with similarity scores,
  for auditability — a lender or auditor must be able to check what the
  answer was actually grounded in.
- Any corpus document not yet confirmed by Legal must be marked
  `NEEDS_LEGAL_VERIFICATION` in frontmatter and the system must say so
  explicitly rather than repeat an unconfirmed figure as fact.

### 5.4 Non-functional requirements

| Requirement | Target | Notes |
|---|---|---|
| F-001 real-time scoring latency | <500ms p95 | Onboarding-time path; must be fast. |
| F-003 explanation latency | <500ms | Bundled into the scoring call. |
| RAG combined retrieval+generation latency | <500ms p95 (aspirational) | Async WhatsApp-style chat; a few seconds is acceptable UX here, unlike the scoring path — see README for why this target is knowingly not met and why that's judged acceptable. |
| Governance gates | Must block deploy | CI fails the build if Gate A (MLOps thresholds) or Gate B (RAG quality) fail. |
| Secrets | Never committed | `.env` files gitignored everywhere; verified per commit. |
| PII | Never persisted beyond what's needed | Normalized UPI signals only; no raw account-holder name/PAN/address written to disk. |

## 6. Governance gates

| Gate | Owner | Pass criteria |
|---|---|---|
| Technical Review | Data Science | F-001 AUC ≥0.82, Risk-Trend ROC-AUC ≥0.96, F-003 latency <500ms — automated in `tests/test_mlops_gates.py` (Gate A). |
| Fairness Audit | Risk & Compliance | F-012: DPD ≤0.05 and DIR ≥0.80 for gender, geography, and income_band (each independently). EOD ≤0.05 is the target but is **not mathematically achievable** for geography/income_band when true base rates differ this much (Kleinberg/Chouldechova impossibility result) — this specific gap requires an explicit human sign-off decision, not an automated pass, and the test suite encodes that as a documented skip rather than a silent pass. |
| Business & DPDP Sign-off | PM + Legal | Every corpus policy document's `legal_signoff_status` must be `approved` before that document can ground a live borrower-facing answer used in a lending decision. Currently `pending`/`NEEDS_LEGAL_VERIFICATION` — open item, see Section 8. |
| Production Approval | MLOps | CI/CD pipeline green (Gate A + Gate B) required before deploy; currently enforced via `.github/workflows/deploy.yml`. |

**Non-negotiables**, regardless of time pressure:
- The RAG coach never answers a compliance/policy question without retrieval
  grounding.
- No governance threshold gets quietly lowered to make a gate pass.
- No unverified legal figure gets asserted as settled fact.
- Every demo-grade shortcut gets flagged explicitly, in the code and in
  README's "what's real vs demo-grade" table — never silently presented as
  production-ready.

## 7. Out of scope for this build

- Real production lending decisions on real user data — this build trains
  and validates on synthetic UPI data (with deliberately injected proxy
  bias, so F-012 has something real to audit) plus one real Setu sandbox
  mock profile pulled live for integration verification, not a real
  borrower's real financial history.
- Formal FIU (Financial Information User) licensing / Sahamati onboarding —
  required before this integration could legally handle a real user's real
  AA consent in production; FinBuddy is currently a TEST-scoped sandbox
  integration only.
- WhatsApp voice-note transcription — the ASR pipeline (Whisper + intent
  classifier) is real and tested on text, but WhatsApp delivers voice notes
  as Opus/OGG, which the current ASR module can't decode without an
  external decoder (`ffmpeg`) not yet added to the deployment. A voice note
  today gets an honest "please type instead" reply, not a broken
  transcription.
- Per-user personalization in the WhatsApp coach (looking up a borrower's
  own score/factors by phone number) — no phone-to-profile store exists
  yet; every WhatsApp reply currently uses the general (non-personalized)
  coaching path.
- A Conformer ASR model trained from scratch, per the original brief's F-9
  naming — out of reach for this build's timeline; a pretrained multilingual
  Whisper model is integrated instead, clearly flagged as such.

## 8. Open items before real production use

1. Legal sign-off on all corpus policy documents.
2. Risk & Compliance sign-off on the geography/income_band equalized-odds
   gap (Section 6).
3. Formal FIU licensing/Sahamati onboarding for the Setu AA integration.
4. Retrain F-001/F-003/F-006/Risk-Trend on real, consented Setu AA data
   before any real lending decision relies on them.
5. Add an OGG/Opus decoder to the RAG service deployment to enable real
   WhatsApp voice-note transcription.
6. Design and build a phone-number-to-borrower-profile lookup so WhatsApp
   coach replies can be personalized with the borrower's actual score and
   factors.

## 9. Success metrics (once live with real users)

Not measurable yet (no real users exist for this build) — stated here as
the metrics production rollout should be judged against, not as achieved
numbers:

- % of scoring decisions where the borrower views their explanation
  (F-003 engagement).
- % of WhatsApp coach questions resolved without human escalation, vs. the
  0.70-confidence-gate escalation rate.
- Fairness metrics (DPD/DIR/EOD) monitored on real portfolio data, not just
  the synthetic audit baseline.
- Drift (PSI/CUSUM) on real scoring traffic, replacing the current
  simulated/synthetic drift-report scenarios.
