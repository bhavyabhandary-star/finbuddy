---
doc_type: policy
regulator: DPDP
effective_year: 2025
audience: internal_audit
last_verified: 2026-08-02
legal_signoff_status: pending
source_note: >
  Content compiled from the program brief's legal research summary, not
  independently re-verified against a primary source in this pipeline run.
  Route through Legal before go-live.
---

# DPDP Rules, 2025 — Consent Managers

## What a Consent Manager is

A Consent Manager is an interoperable platform, registered under the DPDP
framework, through which a person can give, review, and withdraw consent
for how their personal data is shared and used — across different data
fiduciaries, not just one app. It functions as a neutral layer the person
controls, rather than each company running its own siloed consent record.

Setu's Account Aggregator role is conceptually adjacent to this: it
already operates as a consent-based data-sharing intermediary in the
financial data space. FinBuddy should not assume Setu's AA consent flow
*is* a DPDP Consent Manager without confirming that status, since AA and
DPDP Consent Manager registration are governed by different frameworks
(RBI's AA framework vs. the DPDP Rules) even though they address a similar
problem.

## Two obligations specific to Consent Managers

1. **7-year consent record retention.** A Consent Manager must retain
   records of the consent itself — what was agreed to, when, and any
   subsequent withdrawal — for 7 years.
2. **No visibility into the underlying shared data.** A Consent Manager's
   role is to manage the *consent artifact*, not to access or read the
   *data* that consent authorizes moving between parties. It is
   structurally kept blind to the actual personal data changing hands.

## Why point 1 gets confused with a different rule (and why that matters)

It's easy to conflate "Consent Managers retain consent records for 7
years" with a broader claim like "financial records must be retained for
7 years." These are two separate obligations from two separate
regulators, and FinBuddy's own documentation should not blur them:

- The **7-year consent-record retention** duty above belongs to a
  Consent Manager specifically, under the DPDP Rules, and is about
  records *of consent*, not the underlying financial data.
- Separately, **KYC and financial transaction record retention** is
  governed by RBI/PMLA requirements, not the DPDP Rules. See
  `dpdp_vs_pmla_retention.md` for why this needs its own verified figure
  from Legal before FinBuddy states a specific retention period for
  transaction data itself.

## What this means for FinBuddy specifically

If FinBuddy's consent flow is ever formally registered as (or routed
through) a DPDP Consent Manager, the 7-year consent-record duty applies to
FinBuddy's own consent logs. If FinBuddy instead relies on Setu's AA
consent artifact without separate Consent Manager registration, this
specific obligation may not attach directly to FinBuddy — that
determination needs Legal sign-off, not an engineering assumption either
way.
