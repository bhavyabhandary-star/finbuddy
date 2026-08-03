# FinBuddy — EICTA Curriculum Alignment Plan

Maps FinBuddy's actual build to the EICTA Consortium program's 6-module
structure (MeitY + IITs/NITs/IIITs joint initiative). This is an honesty
exercise, not a repackaging one: where real work already satisfies a
module's Gate Review, it's cited with a link, not re-described. Where a
module expects a specific *deliverable format* (a GTM plan, a standalone
ethics audit) that doesn't exist yet even though the underlying substance
does, that's flagged as a real gap, not silently assumed done.

## Module 0 (Weeks 0-1) — Pre-Work Foundations

**Curriculum asks for:** Python/data/math bootcamp, AI context building.
Deliverable: 3 raw product concepts. Evaluation: quiz + readiness check.

Not a FinBuddy build phase — this is prerequisite coursework and an
individual quiz/readiness check, not something this repo's artifacts speak
to. No mapping attempted here; flagging instead of guessing at content
from before this project existed.

## Module 1 (Weeks 2-6) — AI/ML Fundamentals

**Curriculum asks for:** Supervised & unsupervised learning, metrics/
pipelines/modelling basics. Product Integration: add the first ML
feature (e.g., prediction engine). Gate Review: weekly update + feasibility
note.

**Already satisfied, real evidence:**
- Supervised: F-001 XGBoost credit-scoring model, real AUC 0.8824 (target
  ≥0.82) — the "first ML feature / prediction engine" this module asks
  for, literally.
- Unsupervised: F-006 Isolation Forest anomaly detector, real precision/
  recall against injected synthetic anomalies.
- Metrics/pipeline basics: `scoring_service/features/feature_engineering.py`
  (shared train/serve feature schema), `evaluate_classification.py`
  (accuracy/precision/recall/confusion matrix, added this session).
- See [architecture.md](architecture.md) section 4 for the full models
  table with real held-out metrics.

**Gate Review format:** [module1_feasibility_note.md](module1_feasibility_note.md) —
written as a retrospective, including the real false-starts (initial F-001
AUC shortfall, root-caused and fixed; the blocked `shap` dependency
workaround), not just the end-state metrics.

## Module 2 (Weeks 7-11) — LLMs, GenAI & Agentic

**Curriculum asks for:** Prompting, RAG, LangChain, toolchains, agentic
workflows. Product Integration: add a GenAI/agentic response layer. Gate
Review: prototype demo + use-case articulation.

**Already satisfied, real evidence:**
- RAG: real pgvector retrieval over a 10-document policy/coaching corpus,
  paragraph/header-aware chunking, `BAAI/bge-small-en-v1.5` embeddings.
- Prompting: `rag_service/main.py`'s `SYSTEM_PROMPT_TEMPLATE` — a strict,
  grounding-only prompt with explicit compliance rules, real-Groq-tested.
- Agentic decision-making: the 0.70-confidence-gate escalation IS an
  agentic decision (answer vs. hand off to a human), verified live via
  WhatsApp (see README's real Twilio exchange logs).
- Live demo: real WhatsApp round-trip through Twilio, real customer PWA
  chat — not a screenshot mockup.

**Honest gap:** this was built with direct API integration (FastAPI +
`asyncpg`/pgvector + the Groq SDK), not LangChain specifically — worth
naming explicitly if the program's rubric expects LangChain by name rather
than judging the RAG/agentic behavior itself. "Toolchains" in the broader
agent-framework sense (tool-calling, multi-step agent loops) also isn't
built — the RAG coach's only "tool" is retrieval, not a general
tool-use loop.

## Module 3 (Weeks 12-16) — AI Product Management

**Curriculum asks for:** PRDs, roadmaps, ROI frameworks, strategy
documentation. Product Integration: submit full PRD + GTM plan. Gate
Review: strategy review.

**Already satisfied, real evidence:**
- Full PRD: [PRD.md](PRD.md) — problem, users, regulatory context,
  feature requirements, architecture requirements, governance gates,
  explicit out-of-scope, open items, success metrics, and an MLOps
  maturity self-assessment.

**GTM plan:** [gtm_plan.md](gtm_plan.md) — target segments in adoption
order, value proposition per side of the market, an illustrative (not
negotiated) monetization model, launch sequence, and risks named plainly
(explicitly not a validated business model — no customer discovery has
happened yet, stated as such rather than implied otherwise).

## Module 4 (Weeks 17-20) — MLOps & Deployment

**Curriculum asks for:** Pipelines, versioning, monitoring. Product
Integration: deploy MVP on cloud (AWS/HuggingFace). Gate Review:
architecture diagram + test result.

**Already satisfied, real evidence — this module is the most complete:**
- Architecture diagram: [architecture.md](architecture.md) section 1
  (mermaid system diagram) and section 3 (data pipeline diagram).
- Cloud deployment: three live HuggingFace Spaces (scoring, RAG coach,
  customer PWA) — real URLs in README, all verified responding.
- Pipelines: GitHub Actions CI/CD, gated on tests, real green runs.
- Versioning: git/git-LFS for model artifacts, `registry.py`'s real
  git-derived lineage, GHCR container images tagged by commit SHA.
- Monitoring: PSI+CUSUM drift reports, real audit logs on every scoring/
  coach interaction.
- Test result: `pytest tests/ -v` — 28 passed, 8 skipped (each skip
  documented, not silently ignored) as of this session.

No real gap here — this module's specific deliverable formats
(architecture diagram, test result) already exist as committed artifacts.

## Module 5 (Weeks 21-24) — Leadership, Ethics & Scaling

**Curriculum asks for:** Governance, risk management, ethical AI &
organisational adoption. Product Integration: scaling roadmap + ethics
audit. Gate Review: org plan + risk mitigation.

**Already satisfied, real evidence:**
- Ethical AI: F-012 Fairlearn audit — real demographic parity/disparate
  impact/equalized-odds figures across gender, geography, income band,
  with the geography/income_band equalized-odds gap explicitly flagged as
  a human Risk & Compliance sign-off item (not silently passed), per the
  Kleinberg/Chouldechova impossibility result.
- Governance: PRD.md section 6 (governance gates table, ownership,
  non-negotiables).
- Risk mitigation: PRD.md section 8 (open items — legal sign-off, FIU
  licensing, retraining on real data, ffmpeg for voice notes, phone-to-
  profile lookup) and section 7.1 (MLOps maturity gaps named with reasons,
  not hidden).

**Org plan + risk mitigation + ethics audit:** [ethics_and_scaling.md](ethics_and_scaling.md) —
repackages the real F-012 figures precisely (including a correction: an
earlier draft of PRD.md's governance table implied gender passed
post-mitigation on the deployed model; it doesn't — only geography/
income_band are part of the deployed joint mitigation, gender's deployed
DPD/EOD still fail, and that distinction is now stated accurately in both
documents), a risk-mitigation table with named owners, a 5-gate scaling
roadmap, and an org decision-rights table.

## Summary

All three previously-identified gaps are now closed:
[gtm_plan.md](gtm_plan.md) (Module 3), [ethics_and_scaling.md](ethics_and_scaling.md)
(Module 5), and [module1_feasibility_note.md](module1_feasibility_note.md)
(Module 1's weekly-update format specifically). Modules 1 and 4 were
already fully covered by existing artifacts. The one deliberately
un-closed gap remains Module 2's LangChain naming — retrofitting a
LangChain layer just to match a tool name-check wasn't done; the
underlying RAG/agentic behavior is real and demoable, and naming the
actual stack honestly in a submission is safer than adding a framework
dependency purely for rubric-matching.
