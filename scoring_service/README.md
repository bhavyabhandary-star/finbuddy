---
title: FinBuddy Scoring
emoji: 🏦
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8001
pinned: false
---

# FinBuddy Scoring Service

Real-time credit scoring for gig-economy UPI profiles: F-001 (XGBoost
credit score), F-003 (native Tree SHAP explainability), F-006 (Isolation
Forest anomaly pre-check), Featured Risk-Trend classifier, F-012 (Fairlearn
fairness-mitigated approval decision), and F-007/9 (Hindi/Tamil voice
intent classification).

**Trained and evaluated entirely on synthetic data** -- no real Setu
Account Aggregator data exists for this project yet (see
`setu_integration/` for the real sandbox integration code, which is
functional but untested end-to-end pending sandbox credentials). Every
metric this service reports is a statement about the synthetic generator,
not real gig-worker repayment behavior. Do not use this for real lending
decisions without retraining on real, consented data first.

API docs: `/docs` once running.

Required secrets (set via this Space's Settings -> Repository secrets, or
locally in a `.env` file, never committed): none required for scoring
itself. `SETU_*` variables are only needed to run the real Setu AA sandbox
integration script (`setu_integration/fetch_real_profile.py`), not the
serving API.

Governance: see `models/artifacts/f012_fairness_audit.json` for the full
fairness audit. Two items (geography/income_band equalized-odds-difference)
require human Risk & Compliance sign-off before production use rather than
being automatically gated -- see that file's `recommended_gate_a_interpretation`
key for why (a mathematical base-rate tension, not an oversight). The full
governance test suite (Gate A) lives in the main FinBuddy monorepo at
`tests/test_mlops_gates.py`, not in this Space, which only contains the
deployable scoring_service subtree.
