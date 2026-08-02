# FinBuddy Data Catalog

Closes part of the "data catalogue" / "lineage tracking" gaps flagged in
`docs/PRD.md` section 7.1 -- a real inventory of every dataset this project
actually produces or consumes, not a fabricated one. There is no data lake
or feature-store system behind this (see PRD 7.1); this is a hand-maintained
but accurate description of what exists on disk and where it comes from.

## 1. Synthetic UPI dataset (`scoring_service/data/synthetic_upi_dataset.csv`)

- **Source:** `scoring_service/data/generate_synthetic_upi_data.py`, fully
  deterministic (`RNG_SEED = 42`, `N_USERS = 10_000`, `ANOMALY_FRACTION = 0.03`)
  -- regenerating produces a byte-identical file, verified via SHA-256
  comparison across runs (see the CI `test` job's own comment on this).
- **Gitignored, regenerable** -- not committed, since it's fully reproducible
  from the generator script and would otherwise bloat the repo.
- **Not real data.** No real Setu AA pull backs this file. Every metric
  computed from it (F-001 AUC, F-012 fairness figures) is a statement about
  the generator, not real gig-worker repayment behavior.
- **Schema** (one row per synthetic gig worker):

  | Column | Type | Description |
  |---|---|---|
  | `avg_monthly_income` | float | Mean monthly UPI credit volume, INR |
  | `income_regularity_score` | float, 0-1 | Higher = more regular month-to-month income (inverse coefficient of variation) |
  | `tx_count_30d` | int | UPI transaction count, trailing 30 days |
  | `merchant_diversity` | int | Distinct merchants/counterparties, 30 days |
  | `balance_dip_frequency` | int | Times/month balance fell below a low-buffer threshold |
  | `b2b_ratio` | float, 0-1 | Share of inflow that is B2B/business receipts vs. consumer/gig-platform payouts |
  | `avg_transaction_size` | float | Mean UPI transaction amount, INR |
  | `tenure_months` | int, 1-12 | Months of UPI history available (AA consent window) |
  | `gender`, `geography`, `income_band` | categorical | Protected attributes, used ONLY for the F-012 fairness audit, never as model features |
  | (repayment outcome label) | binary | Used to train/validate F-001; base rates deliberately differ by geography/income_band so F-012 has a genuine proxy-bias problem to catch, not a strawman |

## 2. Synthetic Risk-Trend dataset (`scoring_service/data/synthetic_risk_trend_dataset.csv`)

- Same generator and determinism guarantee as above.
- Two 6-month windows (early/late) per synthetic worker, with a controlled
  improving/decaying trend label, feeding the Risk-Trend logistic
  regression. Feature columns are `delta_*` versions of the 8 UPI signals
  above (see `risk_trend_metrics.json`'s `features` list for the exact set).

## 3. Real Setu AA sandbox profile (`scoring_service/data/setu_real_profiles.jsonl`)

- **Source:** `scoring_service/setu_integration/fetch_real_profile.py`, a
  real consent → approval → data-session → normalize → score pipeline
  against Setu's live sandbox (`fiu-sandbox.setu.co`) -- see
  `setu_integration/client.py`'s docstring for exactly what was verified.
- **Gitignored** -- this is real output data, not source code, and (unlike
  the synthetic CSVs) isn't regenerable deterministically since it depends
  on a live human-approved consent each time.
- **No PII.** Only `user_id` (an AA `linkRefNumber` UUID, not a phone number
  or name), the 8 normalized signals, `source` (`"setu_aa_sandbox"`), and
  `fetched_at`. Raw account-holder fields from Setu's response (name, PAN,
  address) are read by `normalizer.py` only to derive the 8 signals and are
  never persisted.
- **Schema:** identical to the synthetic dataset's 8 signal columns (by
  design -- `normalizer.py` maps Setu's real FI data schema onto the exact
  same column set `feature_engineering.py` expects, so every downstream
  model treats a real profile identically to a synthetic one), plus
  `source` and `fetched_at`.

## 4. RAG policy/coaching corpus (`rag_service/finbuddy_rag_corpus/`)

- 10 markdown documents across `policy/`, `coaching/`, `model_cards/`.
- Each has real frontmatter metadata: `doc_type`, `regulator`,
  `effective_year`, `audience`, `last_verified`, `legal_signoff_status`.
  This IS a real, if small, data catalogue for the corpus specifically --
  the gap noted in PRD 7.1 is that the *training* data (items 1-3 above)
  doesn't have equivalent structured metadata alongside it, only this
  document.
- `dpdp_vs_pmla_retention.md` is marked `NEEDS_LEGAL_VERIFICATION` --
  correcting a real conflation error (a Consent Manager's 7-year
  consent-record retention duty vs. KYC/financial-record retention, which
  is governed separately and unconfirmed) -- see README for the full story.

## 5. Runtime audit logs (gitignored, not datasets in the training sense)

- `scoring_service/logs/scoring_audit.jsonl` -- every real-time scoring
  decision (inputs, outputs, latency), written by
  `scoring_service/api/audit_log.py`.
- `rag_service/logs/coach_audit.jsonl` -- every coach interaction from both
  the HTTP API and the WhatsApp webhook (query, answer, sources,
  escalation flag, latency), written by `rag_service/audit_log.py`.
- Local, append-only JSONL files, not a durable multi-region log store --
  see PRD 7.1's "audit logs" entry for the honest scope of this.

## Model artifact lineage

See `scoring_service/models/registry.py` (`python -m scoring_service.models.registry`)
for real per-artifact lineage: git commit hash + commit date for every
trained model file, pulled from `git log`, alongside that model's own real
metrics -- not a fabricated version history.
