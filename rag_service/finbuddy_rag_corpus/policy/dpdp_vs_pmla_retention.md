---
doc_type: policy
regulator: DPDP
effective_year: 2025
audience: internal_audit
last_verified: 2026-08-02
legal_signoff_status: NEEDS_LEGAL_VERIFICATION
source_note: >
  This document exists specifically to prevent a conflation error found in
  earlier drafts of this program's materials. It intentionally does NOT
  assert a specific retention-period figure for KYC/financial transaction
  records as fact. Do not embed a firm number here without Legal sign-off.
---

# Data Retention: Two Separate Obligations, Not One

Earlier drafts of FinBuddy's compliance materials described "7 years" as a
single retention figure covering both consent records and financial/KYC
data. **This is a conflation of two distinct obligations from two
different regulators, and the corpus/coaching layer must not repeat it.**

## Obligation 1 (settled, see `dpdp_consent_managers.md`)

A DPDP-registered **Consent Manager** must retain records of the consent
itself — not the underlying data — for **7 years**. This is specific to
the Consent Manager role and to consent artifacts.

## Obligation 2 (NOT settled — needs Legal verification)

Separately, **KYC and financial transaction record retention** for lending
activity is governed by **RBI and PMLA (Prevention of Money Laundering
Act) requirements**, not the DPDP Rules. The DPDP Rules also separately
reference a general minimum retention period (on the order of 1 year) for
processing/traffic logs, kept for forensic purposes — a third, distinct
figure from a third angle.

**This document does not state a specific number of years for
KYC/financial-transaction retention, because the actual applicable
RBI/PMLA figure has not been confirmed by Legal at the time of writing.**
Earlier material that stated "7 years" for financial records was
extrapolating the Consent Manager's own retention duty onto an unrelated
obligation — an easy mistake to make, and exactly the kind of error a
RAG-grounded coach must not repeat to a borrower or an internal reviewer
as if it were a verified fact.

## What FinBuddy's systems must do until this is resolved

- Any borrower- or auditor-facing answer about "how long is my data kept"
  must distinguish consent records (7 years, DPDP, Consent Manager-specific)
  from financial/transaction/KYC records (RBI/PMLA-governed, figure
  pending Legal confirmation) from general processing logs (DPDP, roughly
  1 year, also pending confirmation of the exact figure and scope).
- The WhatsApp coach must never state a specific KYC/financial retention
  period as settled fact. If asked, it should give the consent-record
  figure where relevant, note that financial-record retention is governed
  separately by RBI/PMLA, and — per the coach's own grounding rules —
  say it cannot give an unverified specific figure rather than guess.
- This is a live open item for Legal, not an engineering decision. Do not
  close it by picking whichever number looks more complete.
