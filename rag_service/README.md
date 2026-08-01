---
title: FinBuddy RAG Coach
emoji: 💬
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 8002
pinned: false
---

# FinBuddy RAG-Grounded WhatsApp Coach

Retrieval-grounded coaching over FinBuddy's RBI/DPDP policy and borrower
coaching corpus. `POST /api/v1/whatsapp-coach/respond` -- retrieval (pgvector
cosine search, 0.70 confidence gate) -> strict grounded-only system prompt
-> Groq (llama-3.3-70b-versatile) generation -> answer + source metadata
for every retrieved chunk.

**Required secrets** (set via this Space's Settings -> Repository secrets):
- `DATABASE_URL` -- a Postgres 15+ connection string with the `vector`
  extension available (this project uses a free-tier Neon instance; Supabase
  or any pgvector-capable Postgres works). Must already have `knowledge_corpus`
  populated -- run `db_setup.py` then `ingest.py` against it first (from the
  main monorepo, not this Space, which doesn't include the corpus ingestion
  scripts' full context).
- `GROQ_API_KEY` -- free at console.groq.com.

**Honest limitations, not glossed over:**
- The `<500ms` combined retrieval+generation latency target from the
  original spec is NOT met -- measured p95 ~5s across golden test queries.
  Retrieval alone is fast (145ms mean); LLM generation for a complete
  answer is the real cost (549ms mean, up to ~850ms for longer answers).
  Judged acceptable for an async WhatsApp-style chat, unlike the scoring
  service's onboarding-time path (128ms p95, genuinely real-time).
- Two corpus documents are explicitly marked `legal_signoff_status: pending`
  or `NEEDS_LEGAL_VERIFICATION` in their frontmatter -- this content has not
  been checked against primary legal sources by a lawyer, only compiled
  from the program brief's research summary. Route through Legal before
  any real borrower relies on these answers.
