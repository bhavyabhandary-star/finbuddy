# FinBuddy

Credit-scoring and WhatsApp-coaching for gig-economy workers in India, built from UPI
transaction signals (via the Setu Account Aggregator) instead of a traditional credit
history most gig workers were never given the chance to build.

This README covers the production-track build (`scoring_service/` + `rag_service/`).
The original hackathon-prototype n8n demo (`finbuddy_n8n_workflow.json`, `finbuddy_setup.md`)
predates this work and is kept for reference, not part of this system.

Product requirements and scope: [docs/PRD.md](docs/PRD.md). Judge/demo walkthrough:
[docs/demo_script.md](docs/demo_script.md). Dataset inventory: [docs/data_catalog.md](docs/data_catalog.md).

## What's real vs. demo-grade -- read this before trusting any number below

This project targets RBI Digital Lending Directions, 2025 and DPDP Act/Rules, 2025
compliance, so being explicit about what's verified vs. simulated is a functional
requirement here, not a caveat to skim past.

| Component | Status |
|---|---|
| F-001/003/006/012/Risk-Trend models | **Real, trained, tested** -- on synthetic data (no real Setu AA data exists for this project). Every metric below is a statement about the synthetic generator, not real repayment behavior. |
| Setu AA sandbox integration (`scoring_service/setu_integration/`) | **Real, verified end-to-end** against the live sandbox: real OAuth token exchange, real consent creation (HTTP 201), real human approval via the mock-FIP webview, real data-session fetch of mock bank transactions, real normalization, real F-001 scoring. Two real docs-vs-live mismatches were found and fixed in the process (the token-exchange endpoint isn't documented anywhere public; the live API returns `FIstatus` where the docs' own example shows `status`) -- see `setu_integration/client.py`'s docstring for exactly what was empirically confirmed vs. assumed. |
| WhatsApp/Twilio integration (`rag_service/whatsapp_webhook.py`) | **Real, verified end-to-end** against a live Twilio WhatsApp Sandbox -- a real WhatsApp message routes through Twilio to the deployed webhook, through the same retrieval+Groq pipeline as the HTTP coach API, and a real reply lands back in WhatsApp (~9s round trip, confirmed in Twilio's own message logs). Signature validation (`X-Twilio-Signature`) is real, not stubbed. Voice notes are explicitly NOT transcribed: WhatsApp sends Opus/OGG, and the ASR module only reads plain WAV without `ffmpeg` (not installed on the dev machine) -- a voice note gets an honest "please type instead" reply rather than being silently dropped or mistranscribed. |
| F-007/9 voice/intent | Intent classifier: real, tested (100% on a small held-out set, LaBSE embeddings chosen after empirically ruling out a weaker multilingual model on Tamil). ASR: pretrained Whisper-small, only mechanically smoke-tested (no real Hindi/Tamil audio sample was available to validate transcription quality; not wired to WhatsApp voice notes yet either, see row above). |
| RAG corpus + retrieval + WhatsApp coach | **Real**, running against a live Postgres+pgvector (Neon) and a real Groq API key. 20/20 Gate B tests + 6 WhatsApp webhook tests pass, including real (non-mocked) LLM faithfulness tests. |
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

## Real Setu AA integration -- what was actually verified

Every step below is a real, live call against the sandbox at `fiu-sandbox.setu.co`,
not a mock:

1. `POST https://orgservice-prod.setu.co/v1/users/login` (a different host than the
   API itself, undocumented publicly -- found by extracting Setu's own Postman
   collection JSON) exchanges `client_id`/`secret` for a short-lived bearer JWT.
2. `POST /v2/consents` with that token -> real HTTP 201, real consent id, real
   human-approval URL.
3. A human (project owner) opened that URL and approved via Setu's mock-FIP webview,
   using their own real phone number to bypass OneMoney AA's UAT number-whitelisting
   requirement (a real external constraint documented in Setu's own docs -- there is
   no shared pre-whitelisted test number).
4. `POST /v2/sessions` + polling `GET /v2/sessions/:id` -> real `COMPLETED` status
   with real (Setu-sandbox-generated) mock transaction data, already decrypted
   server-side by Setu.
5. Normalized into the 8 UPI signals and scored by the real trained F-001 model:
   **credit score 738, approved, `is_anomalous: true`** (expected -- this mock
   account's pattern differs from the synthetic training distribution, not a defect).

Run it yourself (needs real credentials in `scoring_service/.env`, see
`setu_integration/client.py`'s docstring for exactly how to get them from Bridge):
```bash
python -m scoring_service.setu_integration.fetch_real_profile --vua <mobile>@onemoney
```

## Real WhatsApp integration -- what was actually verified

Real message exchange via the live Twilio Sandbox, confirmed in Twilio's own message
logs (`Messages.json` API), not just "the endpoint returns 200":

```
[10:52:52] inbound  "Why do you need my UPI transaction data?"
[10:53:01] outbound "We need your UPI transaction data to understand your income
                      story, as most gig workers don't have a traditional credit
                      history..." (status: read)

[10:55:34] inbound  "What stock should I invest in this week?"
[10:55:36] outbound "I don't have a confident, verified answer to that from
                      FinBuddy's policy and coaching material. Let me connect you
                      with a human coach who can help directly." (status: read)
```

The second exchange proves two things at once, live: the 0.70 confidence gate
correctly escalates an off-corpus question instead of guessing, AND the coach
correctly declines to give investment advice -- both from the same real test.
The escalation reply is faster (2s vs 9s) because it skips the LLM call entirely,
exactly as designed.

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

**Live.** HuggingFace Spaces (Docker SDK), one Space per service, auto-deployed by
`.github/workflows/deploy.yml` on every push to `master` (build-and-deploy only runs
after Gate A + Gate B both pass). Each deploy builds a fresh, single-commit, git-LFS-tracked
snapshot of the service directory and force-pushes it to the Space -- see the workflow
file's comments for why (two real failed attempts: a plain `git subtree push` fails
against a Space's auto-generated initial commit, and pushing this repo's full history
fails HF's server-side check for binary files committed outside Git LFS).

- **Scoring service**: https://bhavyabhandary-finbuddy-scoring.hf.space (`/docs` for the
  interactive API explorer) -- needs no secrets to run (no DB, no external API).
- **RAG coach service**: https://bhavyabhandary-finbuddy-rag-coach.hf.space (`/docs`) --
  needs `DATABASE_URL` and `GROQ_API_KEY` set directly in *this Space's own* Settings ->
  Variables and secrets (GitHub Secrets only apply to the GitHub Actions workflow itself,
  not to the running container on HuggingFace -- a distinct gap that produced a real
  `Internal Server Error` on first deploy before both were added there too).

Both verified live and working end to end, not just "container is up":
```bash
curl -X POST https://bhavyabhandary-finbuddy-scoring.hf.space/api/v1/score \
  -H "Content-Type: application/json" -d '{"avg_monthly_income":21000,"income_regularity_score":0.81,"tx_count_30d":340,"merchant_diversity":11,"balance_dip_frequency":3,"b2b_ratio":0.12,"avg_transaction_size":95,"tenure_months":6,"geography":"rural"}'
# -> real calibrated score, top-3 SHAP factors, fairness-mitigated decision, ~85ms

curl -X POST https://bhavyabhandary-finbuddy-rag-coach.hf.space/api/v1/whatsapp-coach/respond \
  -H "Content-Type: application/json" -d '{"user_query":"why do you need my UPI data"}'
# -> real Groq-generated, corpus-grounded answer with cited sources

curl -X POST https://bhavyabhandary-finbuddy-rag-coach.hf.space/api/v1/whatsapp-coach/respond \
  -H "Content-Type: application/json" -d '{"user_query":"what is the weather like today"}'
# -> escalate_to_human: true, correctly refuses to guess on an off-corpus question
```

## Known open items before real production use

1. Legal sign-off on all corpus policy documents (`legal_signoff_status: pending` /
   `NEEDS_LEGAL_VERIFICATION` in frontmatter).
2. Risk & Compliance sign-off on the geography/income_band equalized-odds gap.
3. Retrain F-001/F-003/F-006/Risk-Trend on real, consented Setu AA data before any
   real lending decision relies on them -- current metrics describe synthetic data.
4. FinBuddy is not a licensed RBI-regulated FIU (it's a capstone project) -- the Setu
   integration currently uses a placeholder Bridge display name and TEST-scoped
   sandbox credentials. Real production use would require formal FIU
   licensing/Sahamati onboarding before this integration could handle real user
   consent, per Setu's own "moving to production" requirements.
5. OneMoney AA (the default sandbox AA partner) requires pre-whitelisting new test
   phone numbers (1-2 business days via support@setu.co) -- worked around for this
   verification by using a real, already-network-known number, not solved generally.
6. WhatsApp voice-note transcription needs an OGG/Opus decoder (`ffmpeg`) added to
   the `rag_service` deployment -- the ASR pipeline itself (Whisper + intent
   classifier) is real and tested, just not wired to WhatsApp's actual audio codec.
7. No phone-number-to-borrower-profile lookup exists yet, so WhatsApp coach replies
   are never personalized with the user's own credit score/factors -- every reply
   uses the general (non-personalized) coaching path.
