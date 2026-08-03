# FinBuddy — Go-to-Market Plan

**Status:** Capstone business case, not validated market traction. No
customer discovery interviews, signed LOIs, or NBFC partnership have
happened — every number below is a reasoned assumption for the purposes of
this plan, explicitly not asserted as researched fact. Where a figure would
normally come from primary research this document doesn't have, that's
stated rather than invented. Companion to [PRD.md](PRD.md) (what the product
must do) — this document is about who adopts it and how.

## 1. Target segments, in adoption order

**Segment 1 — mid-size NBFCs already lending to gig workers informally.**
These lenders already want this population but currently underwrite them
manually or reject them outright for lack of a credit file. They're the
fastest path to a pilot because the pain (no scoring signal for this
population) is acute and current, not something to be convinced of.

**Segment 2 — gig-platform-embedded lending (Swiggy/Zomato/Uber-style
partnerships).** Higher volume, but requires a platform integration and
platform trust, not just a lender's — a second-stage GTM motion, not a
first pilot, since it depends on Segment 1 proving the model works.

**Segment 3 — direct-to-worker (a FinBuddy-branded lending product).**
Requires FinBuddy itself to hold or partner for a lending license — out of
scope for the foreseeable future given the FIU-licensing gap already
flagged in PRD.md section 7. Listed for completeness, not pursued near-term.

## 2. Value proposition, per side of the market

| For the NBFC lender | For the gig worker |
|---|---|
| A previously unscoreable population becomes scoreable — new addressable market, not just a better model for an existing one | A credit decision they can actually understand (F-003 plain-language factors), not a black-box rejection |
| Every decision is SHAP-explained and fairness-audited (F-012) — reduces disparate-impact/regulatory exposure versus a black-box scorecard | A WhatsApp channel they already use, not a new app to trust and install |
| Consent-based Setu AA data, not scraped/unauthorized data — lower compliance risk under DPDP | Data control: a revocable, purpose-limited consent flow (purpose code 103), not a blanket data grant |

## 3. Monetization model (illustrative, not negotiated)

Per-decision API pricing to the NBFC partner, not a data-sale or
subscription model — ties FinBuddy's revenue directly to decisions actually
made, which is also the easiest model for a pilot-stage partner to justify
internally (variable cost tied to loan volume, not a fixed commitment
before proving the model). A rough illustrative structure:

- **Per-score API call** — flat fee per F-001 scoring decision returned to
  the lender.
- **Per-coach-interaction** (optional add-on) — if the lender wants the
  WhatsApp coach white-labeled into their own borrower communications
  rather than just consuming the score.

No specific rupee figures are given here — a real price point requires
NBFC unit-economics conversations (their cost of manual underwriting today,
their margin per loan) that haven't happened. Asserting a number without
that input would be exactly the kind of unverified claim this project's
whole ethos argues against.

## 4. Launch sequence

1. **Pilot (1 NBFC, capped volume):** real Setu AA data (not synthetic),
   small cohort, F-001 retrained on real outcomes per PRD.md section 8 item
   4 before this stage is entered — the synthetic-trained model deployed
   today is a proof of feasibility, not what a real pilot should score
   real lending decisions with.
2. **Pilot outcome review:** real DPD/DIR/EOD fairness figures on real
   pilot data, compared against the synthetic-audit baseline (PRD success
   metrics, section 9) — go/no-go gate before expanding volume.
3. **Segment 1 expansion:** additional NBFC partners, same product,
   proven model.
4. **Segment 2 exploration:** platform-embedded lending conversations,
   contingent on Segment 1 traction — not started in parallel, since it's a
   materially different (and slower) sales motion.

## 5. Risks to this plan, named plainly

- **Regulatory:** FIU licensing (PRD section 7) is a hard blocker before
  any pilot can use real consented data at scale — this is a timeline risk
  to the whole plan, not a footnote.
- **Model risk:** the synthetic-to-real generalization gap is unverified —
  F-001's real 0.8824 AUC describes the synthetic generator, not
  confirmed real-world gig-worker repayment behavior (README's own
  caveat). Pilot-stage retraining and re-audit is not optional.
- **Adoption risk:** NBFCs underwriting this population manually today may
  have workarounds (informal reference checks, group lending models) that
  are "good enough" for their current risk appetite — the value
  proposition needs validating with real conversations, not assumed.
- **Competitive:** other alternative-data underwriting approaches exist in
  this space; this document does not name specific competitors or claim a
  differentiation that hasn't been benchmarked against them.

## 6. What this plan is NOT

Not a funding pitch deck, not a validated business model, not a
substitute for actual customer discovery. It's a reasoned starting
structure for those conversations — the honest next step is talking to a
real NBFC's underwriting team, not refining this document further in
isolation.
