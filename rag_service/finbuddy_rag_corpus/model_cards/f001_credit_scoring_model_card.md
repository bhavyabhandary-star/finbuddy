---
doc_type: model_card
regulator: null
effective_year: 2025
audience: internal_audit
last_verified: 2026-08-02
legal_signoff_status: pending
source_note: >
  Numbers below are pulled directly from this pipeline's own generated
  artifacts (scoring_service/models/artifacts/*.json), not estimated or
  recalled from memory. Regenerate this document if those artifacts change.
---

# Model Card: F-001 Credit Scoring (+ F-003, F-006, Featured Risk-Trend, F-012)

## F-001 — Credit Score (XGBoost)

- **Approach:** Gradient-boosted trees (XGBoost), isotonic-calibrated,
  mapped to a 300-850 score band.
- **Inputs:** 8 UPI signals only (avg_monthly_income, income_regularity_score,
  tx_count_30d, merchant_diversity, balance_dip_frequency, b2b_ratio,
  avg_transaction_size, tenure_months). Protected attributes (gender,
  geography, income_band) are never model features.
- **Result:** held-out AUC **0.8824** against a governance target of
  **0.82**. Brier score 0.1395. Trained on 8,000 synthetic profiles,
  evaluated on 2,000 held out.
- **Critical caveat:** trained and evaluated entirely on synthetic data —
  no real Setu AA data exists for this project yet. This AUC describes the
  synthetic data generator, not real gig-worker repayment behavior. Do not
  cite this number as evidence of real-world model quality; it is evidence
  the *pipeline* (data → features → model → calibration → gate) works
  correctly.

## F-003 — Explainability (native Tree SHAP)

- **Approach:** XGBoost's built-in Tree SHAP (`pred_contribs=True`), not
  the `shap` Python package — this machine's Application Control policy
  blocks a DLL the `shap` package's numba dependency needs. Native Tree
  SHAP produces the same additive, game-theoretically-grounded
  contributions.
- **Result:** single-row explanation latency measured at **36ms**,
  against a 500ms target.

## Featured — Risk-Trend Classifier (Logistic Regression, Ridge)

- **Approach:** L2-regularized logistic regression on the *delta* (late
  6-month window minus early 6-month window) of each of the 8 UPI signals.
- **Result:** held-out ROC-AUC **0.9813** against a governance target of
  **0.96**. Same synthetic-data caveat as F-001 applies.

## F-006 — Anomaly Detection (Isolation Forest)

- **Approach:** Unsupervised Isolation Forest over the 8 UPI signals,
  contamination parameter 0.03. Never sees ground-truth anomaly labels at
  fit time.
- **Result (against synthetic injected anomalies, informational only —
  no governance gate is defined for F-006):** precision **0.8448**,
  recall **0.8909** on 2,000 held-out profiles (55 true synthetic
  anomalies, 58 flagged). Expect materially lower precision against real,
  more diverse anomalous patterns than these three synthetic injection
  types (balance shock, volume spike, merchant collapse).

## F-012 — Fairness Audit (Fairlearn)

Computed separately for gender, geography, and income_band — not one
aggregate figure. Baseline (pre-mitigation) failed governance thresholds
(demographic_parity_difference ≤0.05, equalized_odds_difference ≤0.05,
disparate_impact_ratio ≥0.80) on all three cuts.

**Deployed mitigation:** `ThresholdOptimizer` (demographic parity) fit
jointly on the geography × income_band intersection.

| Cut | DPD (≤0.05) | DIR (≥0.80) | EOD (≤0.05) |
|---|---|---|---|
| geography | 0.0053 ✅ | 0.9896 ✅ | 0.2887 ❌ |
| income_band | 0.0225 ✅ | 0.9564 ✅ | 0.2693 ❌ |
| gender (isolated demo) | 0.0153 ✅ | 0.9720 ✅ | 0.0469 ✅ |

Accuracy cost of the deployed mitigation vs. the unmitigated baseline:
**5 percentage points** (baseline accuracy minus mitigated accuracy).

**Why geography/income_band's equalized-odds-difference stays elevated:**
true repayment base rates differ substantially by group in this data
(rural 18.9% vs. urban 68.3%; low-income 37.4% vs. high-income 81.7%).
When base rates differ this much, demographic parity and equalized odds
cannot both be driven near zero simultaneously — this is a mathematical
property of the data (Kleinberg, Mullainathan & Raghavan 2016;
Chouldechova 2017), not an unresolved bug. **This is flagged as requiring
Risk & Compliance sign-off, not resolved automatically** — which fairness
criterion a lending product should prioritize when true risk differs by
group is a policy decision.

**Gender is different:** true base rates are ~equal across gender groups
(~50%), so an isolated gender-only mitigation passes all three metrics
cleanly. It is not yet part of the single deployed model because the full
three-way joint mitigation hit a data-sparsity crash (the "other" gender ×
rural × high-income cell had only one outcome class present in a 10,000-row
synthetic set) — a small-data artifact expected to resolve with a larger
cohort, not a fairness-theory dead end.

**income_band caveat:** income_band is derived from the model's single
strongest legitimate predictor (avg_monthly_income). A passing DPD/DIR
number here should not be read as a clean bias fix without a human
fairness/compliance reviewer confirming it reflects acceptable risk-based
differentiation rather than parity achieved by ignoring real repayment-risk
signal.

## Governance gate status (Gate A)

Automated pass: F-001 AUC, Risk-Trend AUC, gender DPD/DIR/EOD (isolated
demo), geography DPD/DIR, income_band DPD/DIR.

Requires human sign-off, not automated: geography EOD, income_band EOD.

See `tests/test_mlops_gates.py` for the executable version of this table —
the two human-sign-off items appear there as explicit `SKIP`s with a
`requires_human_signoff` reason, not as silent passes.
