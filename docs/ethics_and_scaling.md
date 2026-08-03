# FinBuddy — Ethics Audit, Scaling Roadmap & Org Plan

Repackages real, already-computed content (F-012 fairness audit, PRD
governance sections) into the shape EICTA Module 5 expects (ethics audit +
scaling roadmap + org plan + risk mitigation) — this is organization, not
new analysis. See [PRD.md](PRD.md) section 6 for the governance-gate table
this draws from, and `scoring_service/models/artifacts/f012_fairness_audit.json`
for the underlying numbers.

## 1. Ethics audit — real figures, precisely stated

Three protected attributes audited independently (never one aggregate
"fairness score"): gender, geography, income_band. Two conditions matter —
the **baseline** (no mitigation) and the **deployed** model (Fairlearn
`ThresholdOptimizer`, demographic-parity constraint, fit jointly on the
geography × income_band intersection).

| Attribute | Baseline DPD | Deployed DPD | Deployed DIR | Deployed EOD | Gate status |
|---|---|---|---|---|---|
| Geography | 0.6053 (fails badly) | **0.0053** (passes ≤0.05) | **0.99** (passes ≥0.80) | 0.2887 (fails ≤0.05) | DPD/DIR hard-gated & passing; EOD is a documented human-signoff item, not automatable — see below |
| Income_band | 0.4834 (fails badly) | **0.0225** (passes) | **0.96** (passes) | 0.2693 (fails) | Same as geography, plus a distinct caveat (below) |
| Gender | 0.0822 (fails) | **0.1168 (still fails — not part of the deployed fit)** | 0.81 (passes) | 0.1239 (fails) | NOT gated on the deployed model — see below |

**Why geography/income_band's EOD can't reach 0.05, and why that's not a
bug:** their true repayment base rates differ enormously (rural 18.9% vs.
urban 68.3%; low income 37.4% vs. high income 81.7%). When base rates
differ this much, demographic parity and equalized odds are provably not
simultaneously satisfiable at a strict threshold (Kleinberg, Mullainathan &
Raghavan 2016; Chouldechova 2017) — a property of the data, not an
unfixed defect. This project prioritizes demographic parity (the standard
disparate-impact/fair-lending criterion) and reports the resulting EOD gap
as an explicit **Risk & Compliance policy decision**, not something
automated.

**Income_band's specific caveat, stated plainly, not glossed over:**
income_band is derived from the model's single strongest legitimate
feature (`avg_monthly_income`). Passing DPD/DIR here should NOT be read as
"bias fixed" without a human reviewer confirming this reflects acceptable
risk-based differentiation rather than parity achieved by suppressing a
real repayment-risk signal. This is flagged in the audit JSON itself
(`income_band_caveat`), not just in this document.

**Gender's honest status — the nuance this document exists partly to get
right:** gender's DPD/EOD on the **actual deployed model** (0.1168 / 0.1239)
still fail their thresholds; only DIR passes (0.81). A **separate, not
deployed** demonstration — mitigating gender in isolation — proves all
three metrics pass (DPD 0.0153, DIR 0.972, EOD 0.0469), because gender's
true base rates are nearly equal across groups (male 50.06%, female
49.95%, other 50.92%), unlike geography/income_band. That isolated result
proves the gender gap is *fixable in principle*; it does not mean the
currently deployed model has fixed it. A prior draft of this project's own
PRD stated this imprecisely (implying all three attributes passed
post-mitigation) — corrected here and in PRD.md section 6 once this
distinction was checked against the real audit JSON rather than assumed
from memory.

One more caveat worth carrying into any real decision: the "other" gender
category has only 44 people in this holdout set, and its 95% confidence
interval (0.470–0.758) overlaps the population approval rate (0.508) — the
observed gap for that group is not statistically distinguishable from
sampling noise at this sample size. More data is needed before treating
that specific figure as a real disparity.

## 2. Risk mitigation plan

| Risk | Mitigation status | Owner |
|---|---|---|
| Geography/income_band EOD gap | Documented, not silently passed; requires explicit Risk & Compliance sign-off before this model scores real lending decisions | Risk & Compliance (PRD section 6) |
| Gender gap on the deployed model | Not yet mitigated in production; an isolated fix is proven feasible — deciding whether/how to extend the deployed mitigation to include gender is an open design decision, not yet made | Data Science + Risk & Compliance |
| Synthetic-only training data | F-001/F-003/F-006/Risk-Trend must be retrained on real, consented Setu AA data before any real lending decision relies on them | Data Science (PRD section 8, item 4) |
| No FIU license | Blocks any real-data pilot at scale; formal Sahamati onboarding required first | Legal/Compliance (PRD section 7) |
| Legal sign-off on policy corpus | 10 RAG corpus documents currently `pending`/`NEEDS_LEGAL_VERIFICATION` — must reach `approved` before grounding a real borrower-facing compliance answer | Legal (PRD section 8, item 1) |
| No access controls on live APIs | Deliberate for demo accessibility; must be added before any real-data deployment (PRD section 7.1) | Engineering |
| No audit trail beyond local logs | Real audit logging now exists (`scoring_service/api/audit_log.py`, `rag_service/audit_log.py`) but is local/append-only, not a durable compliance-grade log store | Engineering |

## 3. Scaling roadmap (org adoption sequence)

Mirrors [gtm_plan.md](gtm_plan.md)'s launch sequence, framed here as
organizational gates rather than sales stages:

1. **Gate 0 (current state):** synthetic-data proof of feasibility, all
   governance gates automated where mathematically possible, real Setu/
   WhatsApp integration verified end-to-end in sandbox. No real user data
   has been scored.
2. **Gate 1 — real-data pilot readiness:** requires FIU licensing (Legal),
   retrained models on real consented data (Data Science), and the
   gender-mitigation design decision resolved (Data Science + Risk).
3. **Gate 2 — pilot go/no-go:** real DPD/DIR/EOD figures on real pilot
   data compared against this synthetic baseline; Risk & Compliance
   sign-off on the geography/income_band EOD gap using real, not
   synthetic, base rates.
4. **Gate 3 — expansion:** additional NBFC partners (Segment 1 in the GTM
   plan), same governance gates re-run on each new cohort, not assumed
   to still hold.
5. **Gate 4 — platform-embedded lending (Segment 2):** contingent on Gate
   3 traction; a materially different integration and trust model, not
   pursued in parallel with Gate 1-3.

## 4. Org plan — decision rights

| Decision | Who decides | Not decided by |
|---|---|---|
| Whether geography/income_band's EOD gap is acceptable to ship | Risk & Compliance, explicitly, per lending program | An automated test (deliberately — see PRD section 6) |
| Whether to extend the deployed mitigation to include gender | Data Science + Risk & Compliance jointly | Engineering alone |
| Whether a corpus document is legally accurate enough to ground borrower answers | Legal | Product/Engineering |
| Whether to move from synthetic to real training data | Data Science, gated on FIU licensing (Legal) being resolved first | Not a unilateral Data Science call — licensing blocks it regardless |
| Whether to pursue Segment 2 (platform-embedded) GTM | Business/Product, gated on Segment 1 pilot outcomes | Not started speculatively in parallel |
