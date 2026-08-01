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
  run. Route through Legal before go-live, per the Business & DPDP
  Sign-off governance gate.
---

# RBI Digital Lending Directions, 2025 — Fund Routing Requirement

The RBI Digital Lending Directions, 2025 (in force from 8 May 2025) impose
a strict fund-routing rule on every digital lending arrangement that
involves a Lending Service Provider (LSP) such as FinBuddy operating
alongside a Regulated Entity (RE) — a bank or NBFC.

## The rule

All loan disbursals must move directly from the Regulated Entity to the
borrower's bank account. No LSP-controlled pass-through account may sit in
that path. Symmetrically, all loan repayments must move directly from the
borrower back to the Regulated Entity. The LSP is not permitted to collect,
pool, or momentarily hold either the disbursed principal or the repayment
proceeds.

This closes off a specific failure mode regulators observed in the digital
lending market before these Directions: LSPs collecting repayments into
their own accounts and forwarding them to lenders on a delay, which both
obscured the true cost of credit to the borrower and created a window
where LSP insolvency could strand borrower repayments before they reached
the actual lender.

## What this means for FinBuddy specifically

FinBuddy acts as an LSP: it originates the credit-scoring signal (F-001),
explains it (F-003), and coaches the borrower, but it is not itself a bank
or NBFC. Every FinBuddy integration with a partner Regulated Entity must
be architected so that:

- The disbursal API call moves money from the RE's account to the
  borrower's account directly (FinBuddy's system may *initiate* or
  *trigger* this call via the RE's rails, but must never be a routing
  intermediary that receives the funds itself, even transiently).
- The repayment collection mechanism (UPI autopay, NACH mandate, etc.) is
  configured to settle directly into the RE's account.
- FinBuddy's own revenue (platform fees, servicing fees) must be
  collected separately from the loan cash flows — never netted out of a
  disbursal or repayment amount before it reaches its destination.

## Why this is a functional requirement, not a formality

Because FinBuddy's outputs feed real lending decisions by banks/NBFCs,
getting this wrong is not a documentation gap — it would put a partner RE
in breach of a binding RBI Direction, with the LSP relationship itself at
risk of being unwound. Any FinBuddy feature that touches money movement
(not just scoring) must be reviewed against this rule specifically, not
assumed compliant because the scoring/coaching layer is compliant.
