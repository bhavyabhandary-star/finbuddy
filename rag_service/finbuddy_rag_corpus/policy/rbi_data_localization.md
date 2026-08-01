---
doc_type: policy
regulator: RBI
effective_year: 2025
audience: internal_audit
last_verified: 2026-08-02
legal_signoff_status: pending
source_note: >
  Content compiled from the program brief's legal research summary, which
  flagged this specific figure as verified across multiple legal-tracker
  sources with high confidence. Still route through Legal before go-live.
---

# RBI Digital Lending Directions, 2025 — Data Localization and Cross-Border Processing

## The rule

Borrower data collected as part of a digital lending arrangement under
these Directions must be stored on servers located in India. If any
processing of that data occurs outside India (for example, on
infrastructure operated by a vendor with processing capacity abroad), the
data must be deleted from the foreign server and repatriated to India
within 24 hours of that processing completing.

This is a narrower and stricter rule than data localization requirements
seen in some other contexts: it does not merely require a copy to be kept
in India — it requires that data not persist outside India past a
24-hour processing window, full stop.

## What this means for FinBuddy specifically

FinBuddy's architecture — Setu AA feed → FastAPI inference → SHAP +
calibration → PWA/lender API/WhatsApp coach — must keep every stage where
borrower UPI transaction data or derived signals are computed and stored
on India-based infrastructure. This has concrete implications:

- **Model inference (F-001/F-003/F-006):** the scoring service, wherever
  it is hosted, must run on India-region infrastructure for any request
  carrying real borrower UPI signals. A US-region or globally load-balanced
  deployment that might route a request to a non-Indian data center is not
  compliant as-is.
- **RAG/coaching layer (Groq generation call):** if the LLM generation
  step in the WhatsApp coach pipeline is served from infrastructure outside
  India, borrower-specific content passed into that prompt (their credit
  score, SHAP factors, query text) is "processed abroad" for purposes of
  this rule. Confirm the actual data-residency posture of any third-party
  inference API used here before sending real borrower data through it —
  this is a real constraint on vendor choice, not a footnote.
- **Model artifacts and training data:** as long as training uses
  synthetic data (as it does at the time of this writing), this rule
  doesn't bite. It becomes a live constraint the moment real, consented
  Setu AA data is used for training or fine-tuning.

## Why the 24-hour figure matters operationally

This is not a "best effort" or "reasonable time" standard — it is a fixed
24-hour clock starting from when foreign processing occurs. Any vendor or
sub-processor in the data path needs a contractual and technical
commitment to that window, and FinBuddy's own logging needs to be able to
demonstrate compliance with it if audited.
