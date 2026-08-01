# FinBuddy

Credit-scoring and WhatsApp-coaching for gig-economy workers in India, built from UPI
transaction signals (via the Setu Account Aggregator) instead of a traditional credit
history most gig workers were never given the chance to build.

This README covers the production-track build (`scoring_service/` + `rag_service/`).
The original hackathon-prototype n8n demo (`finbuddy_n8n_workflow.json`, `finbuddy_setup.md`)
predates this work and is kept for reference, not part of this system.

## What's real vs. demo-grade -- read this before trusting any number below

This project targets RBI Digital Lending Directions, 2025 and DPDP Act/Rules, 2025
compliance, so being explicit about what's verified vs. simulated is a functional
requirement here, not a caveat to skim past.

| Component | Status |
|---|---|
| F-001/003/006/012/Risk-Trend models | **Real, trained, tested** -- on synthetic data (no real Setu AA data exists for this project). Every metric below is a statement about the synthetic generator, not real repayment behavior. |
| Setu AA sandbox integration (`scoring_service/setu_integration/`) | **Real code**, hits Setu's actual documented API shape -- but untested end-to-end (needs sandbox credentials from bridge.setu.co, which this session didn't have). |
| F-007/9 voice/intent | Intent classifier: real, tested (100% on a small held-out set, LaBSE embeddings chosen after empirically ruling out a weaker multilingual model on Tamil). ASR: pretrained Whisper-small, only mechanically smoke-tested (no real Hindi/Tamil audio sample was available to validate transcription quality). |
| RAG corpus + retrieval + WhatsApp coach | **Real**, running against a live Postgres+pgvector (Neon) and a real Groq API key. 20/20 Gate B tests pass, including real (non-mocked) LLM faithfulness tests. |
| Fairness audit (F-012) | **Real audit, real mitigation, real unresolved item.** Geography/income_band equalized-odds-difference stays above the 0.05 target by mathematical necessity (see below) -- flagged for human Risk & Compliance sign-off, not silently passed. |
| PSI + CUSUM drift monitoring | **Real, tested** (pure numpy, not the `evidently` package -- see `scoring_service/monitoring/drift_report.py` for why). A literal Evidently-branded variant exists but is unverified (untestable on the dev machine; runs in CI on Linux instead). |
| Docker images | Written correctly per best practice, but **not build-tested locally** -- this machine's virtualization is disabled at the firmware level (confirmed via `systeminfo`), so Docker Desktop cannot run here. Verified structurally, not with an actual `docker build`. |
| Live deployment | See "Deployment" below for current status. |

## Architecture

```
Setu AA Feed (consent-based 12-mo UPI pull, normalized to 8 signals)
  -> FastAPI Inference (F-001 + F-006 anomaly pre-check, p95 128ms)
  -> SHAP + Calibration (F-003: top-3 factors + calibrated PD, native XGBoost Tree SHAP)
  -> Consumers: React PWA dashboard / NBFC lender API / WhatsApp coach (RAG-grounded)
```

Two independent services, two independent HuggingFace Spaces (see Deployment):

- **`scoring_service/`** -- F-001 (XGBoost credit score), F-003 (explainability),
  F-006 (Isolation Forest anomaly detection), Featured Risk-Trend classifier, F-012
  (Fairlearn fairness audit + mitigation), F-007/9 (voice/intent), real-time + batch +
  champion/challenger serving.
- **`rag_service/`** -- pgvector-backed retrieval over an RBI/DPDP policy + borrower
  coaching corpus, Groq-generated WhatsApp coach responses, source-cited for
  auditability.

## Real numbers (from this session's actual runs, not projected)

| Gate | Target | Result |
|---|---|---|
| F-001 AUC | ≥0.82 | **0.8824** |
| Risk-Trend ROC-AUC | ≥0.96 | **0.9813** |
| F-003 explain latency | <500ms | **36ms** |
| F-001 real-time scoring p95 | <500ms | **128ms** |
| F-012 fairness (geography/income_band DPD, DIR) | ≤0.05 / ≥0.80 | **Pass** (post-mitigation) |
| F-012 fairness (geography/income_band EOD) | ≤0.05 | **Not met -- human sign-off required, see below** |
| F-012 fairness (gender, isolated) | all three metrics | **Pass** |
| Gate A (`tests/test_mlops_gates.py`) | -- | **6 passed, 2 explicit skips** |
| Gate B (`tests/test_rag_pipeline.py`) | -- | **20/20 passed** (incl. real Groq calls) |
| RAG combined retrieval+generation p95 | <500ms | **~5s -- not met, see below** |

### Why two targets aren't met, and why that's not being hidden

**Fairness (geography/income_band equalized-odds-difference):** these two attributes
have genuinely different true repayment base rates in the data (rural 18.9% vs. urban
68.3%). When base rates differ this much, demographic parity and equalized odds
provably cannot both be driven near zero simultaneously (Kleinberg, Mullainathan &
Raghavan 2016; Chouldechova 2017) -- a property of the data, not an unfixed bug. This
project prioritizes demographic parity (the standard fair-lending / disparate-impact
criterion) and reports the resulting equalized-odds gap as a **policy decision for
Risk & Compliance**, not something a script should resolve either way. See
`scoring_service/models/artifacts/f012_fairness_audit.json` and
`tests/test_mlops_gates.py`'s `requires_human_signoff` skips.

**RAG latency:** retrieval alone is fast (145ms mean). LLM generation for a complete,
useful answer takes 344-852ms even on Groq (one of the fastest LLM inference
providers available) -- the <500ms combined target isn't realistic for a synchronous
external-LLM-API call producing real content. Judged acceptable because this is a
WhatsApp-style async chat, not the onboarding-time scoring path (which genuinely is
fast, at 128ms p95).

## RAG-Grounded Responsible Coaching

The WhatsApp coach (`POST /api/v1/whatsapp-coach/respond`) never answers a
policy/compliance/data-use question without retrieval grounding -- if the top
retrieved chunk's cosine similarity is below 0.70, the request is routed to a human
coach instead of generating an answer (`low_confidence: true`, verified: an
off-corpus test query like "what's the weather" correctly escalates).

Every answer returns the source metadata of every retrieved chunk, for auditability.
The corpus (`rag_service/finbuddy_rag_corpus/`) includes a document
(`dpdp_vs_pmla_retention.md`) specifically marked `NEEDS_LEGAL_VERIFICATION` to
correct a real conflation error from an earlier draft (a Consent Manager's 7-year
*consent-record* retention duty being mistaken for a KYC/financial-record retention
figure, which is actually governed separately by RBI/PMLA and hasn't been confirmed).
Gate B's faithfulness tests specifically assert the coach states the verified 24-hour
data-repatriation rule correctly and never asserts the unverified retention figure as
fact -- tested against the real deployed Groq model, not just a mock.

## Governance gates

| Gate | Owner | Status |
|---|---|---|
| Technical Review (AUC targets) | Data Science | **Automated, passing** (`tests/test_mlops_gates.py`) |
| Fairness Audit (F-012) | Risk & Compliance | **Partially automated** -- DPD/DIR pass for all three cuts; EOD for geography/income_band needs human sign-off (mathematical tension, documented above) |
| Business & DPDP Sign-off | PM + Legal | **Pending** -- corpus docs marked `legal_signoff_status: pending`/`NEEDS_LEGAL_VERIFICATION` need actual Legal review before go-live |
| Production Approval | MLOps | **CI/CD wired** (`.github/workflows/deploy.yml`), gated on Gate A + Gate B passing |

## Running it yourself

```bash
# Scoring service
python -m scoring_service.data.generate_synthetic_upi_data   # regenerate synthetic data
python -m scoring_service.models.train_credit_score          # F-001
python -m scoring_service.models.fairness_audit               # F-012
uvicorn scoring_service.api.main:app --port 8001

# RAG service (needs DATABASE_URL + GROQ_API_KEY in rag_service/.env)
python -m rag_service.db_setup
python -m rag_service.ingest
uvicorn rag_service.main:app --port 8002

# Tests
pytest tests/ -v
```

## Deployment

Target: HuggingFace Spaces (Docker SDK), one Space per service, deployed via
`git subtree push` in CI once GitHub Secrets are configured -- see
`.github/workflows/deploy.yml`'s header comment for the exact secrets required.

- Scoring service: _pending first deploy_
- RAG coach service: _pending first deploy_

## Known open items before real production use

1. Legal sign-off on all corpus policy documents (`legal_signoff_status: pending` /
   `NEEDS_LEGAL_VERIFICATION` in frontmatter).
2. Risk & Compliance sign-off on the geography/income_band equalized-odds gap.
3. Retrain F-001/F-003/F-006/Risk-Trend on real, consented Setu AA data before any
   real lending decision relies on them -- current metrics describe synthetic data.
4. Verify the Setu AA sandbox integration end-to-end once sandbox credentials exist.
5. Confirm the Setu AA base URL and auth header names against your actual Bridge
   product's Postman collection (documented as unconfirmed in `setu_integration/client.py`).
