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

# DPDP Rules, 2025 — Valid Consent Standard

The Digital Personal Data Protection Rules, 2025 (notified 14 November
2025) set the operative standard for what counts as valid consent to
process a person's personal data, including the UPI transaction data
FinBuddy collects via the Setu Account Aggregator flow.

## The standard

Consent must be:

- **Free** — not obtained under duress, or as a non-negotiable condition
  bundled into an unrelated service the person actually wants.
- **Specific** — tied to a particular, clearly stated purpose. A single
  broad consent covering "all data processing" for unspecified future uses
  does not meet this bar.
- **Informed** — the person must actually understand what they are
  agreeing to, in language and terms they can follow, not buried in dense
  legal text.
- **Unambiguous** — no plausible reading of the consent flow could leave
  genuine doubt about whether the person agreed.
- **Given through clear affirmative action** — the person must actively
  do something to consent (check a box, tap a button explicitly framed as
  consenting). Passive acceptance does not count.

Two things are explicitly *not* valid consent under this standard:
**pre-checked boxes** (consent must be opted into, not opted out of), and
**bundled or vague consent** (rolling multiple distinct purposes into one
blanket approval).

## What this means for FinBuddy specifically

FinBuddy's onboarding flow asks a borrower to consent to a Setu Account
Aggregator data pull covering up to 12 months of UPI transaction history,
for the specific purpose of credit scoring and coaching. To meet this
standard:

- The consent screen must state the specific purpose (credit scoring for
  a loan decision, not a generic "improve your experience" framing) and
  the specific data scope (which FI types, what time window).
- No checkbox may be pre-selected. The borrower must actively tap/check to
  consent.
- If FinBuddy ever wants to use the same data for a second purpose (e.g.,
  aggregate analytics, a different product feature), that needs its own
  specific consent — it cannot ride along on the original credit-scoring
  consent.
- The WhatsApp coaching flow, when it explains "why do you need my UPI
  data" to a borrower who asks, should describe the actual specific
  purpose given at consent time — not a generic privacy-policy summary —
  since that consistency is itself part of what "informed" consent means
  in practice.
