---
doc_type: policy
regulator: RBI
effective_year: 2025
audience: internal_audit
last_verified: 2026-08-02
legal_signoff_status: pending
source_note: >
  Content compiled from the program brief's legal research summary, not
  independently re-verified against a primary RBI source in this pipeline
  run. Route through Legal before go-live.
---

# RBI Digital Lending Directions, 2025 — Default Loss Guarantee (DLG) Cap

## The rule

Where an LSP or other arrangement provides a Default Loss Guarantee (DLG)
to a Regulated Entity — effectively agreeing to absorb some portion of
losses if borrowers default — that guarantee is capped at 5% of the
disbursed loan pool it covers. The existence and terms of any DLG
arrangement must be disclosed publicly, not just to the regulator or
between the contracting parties.

## Why this rule exists

DLG arrangements let an LSP signal confidence in its own credit-scoring
model by putting some of its own capital at risk. Left uncapped and
undisclosed, though, a DLG can quietly shift risk-bearing away from the
Regulated Entity that is supposed to be underwriting the loan, and can
mask how much of the "credit decision" is actually being made by an
unregulated LSP rather than the licensed lender. The 5% cap keeps the LSP's
guarantee as a confidence signal, not a substitute for the RE's own risk
ownership; the public-disclosure requirement keeps borrowers and the
market able to see that the arrangement exists.

## What this means for FinBuddy specifically

FinBuddy itself is a credit-scoring and coaching layer, not (currently) a
capital-bearing party to any loan. But if a future commercial arrangement
with a partner Regulated Entity involves FinBuddy or its parent
organization offering any form of default-loss guarantee to make its
scoring model's outputs more attractive to lenders:

- The guaranteed amount must not exceed 5% of the pool of loans it covers.
- The existence, scope, and terms of that guarantee must be disclosed
  publicly — this is not something that can be handled as a private
  commercial term between FinBuddy and the RE.
- This is a Business & DPDP / Legal sign-off item, not something the
  scoring or engineering team can decide unilaterally — any DLG-style
  commercial term needs to be checked against this cap before it's agreed
  to, not after.
