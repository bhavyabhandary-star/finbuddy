"""POST /api/v1/whatsapp-coach/respond -- RAG-grounded WhatsApp coach.

Pipeline: search_corpus(transcribed_intent, falling back to user_query) ->
if low_confidence, escalate to a human coach WITHOUT calling the LLM at all
-> else build a strict grounded-only system prompt from the retrieved
context + the borrower's own F-001/F-003 signals -> Groq generation ->
return the answer plus every retrieved chunk's source metadata, for
auditability.

Run: uvicorn rag_service.main:app --reload --port 8002
Docs: http://localhost:8002/docs

LATENCY, MEASURED HONESTLY: the program spec's <500ms combined
retrieval+generation p95 target is NOT met, and isn't realistically
achievable for a synchronous call to an external LLM API while producing
complete, useful answers. Measured breakdown (real Groq calls, 5 golden
questions): retrieval 145ms mean / 171ms p95 (fine); generation 549ms mean
/ 813ms p95 (the actual bottleneck, scales with answer length: 200-850
char answers took 344-852ms to generate). Full combined-path benchmark
across 20 calls: p95 5040ms, max 6064ms. This is being reported as-is
rather than quietly claimed as passing -- see the model card for the full
number and rationale. It's judged acceptable because this is a WhatsApp-
style async chat interaction (a few seconds of "typing..." delay is normal
UX there), unlike F-001's onboarding-time scoring call, which genuinely
needs to be fast and is (128ms p95, see scoring_service).
"""

from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rag_service import audit_log, llm_client
from rag_service.retriever import search_corpus

app = FastAPI(
    title="FinBuddy RAG-Grounded WhatsApp Coach",
    description="Retrieval-grounded coaching over FinBuddy's policy/coaching corpus, consumed by n8n / the WhatsApp bot.",
    version="0.1.0",
)

# See scoring_service/api/main.py for why "*" is a deliberate demo-grade
# choice here, not an oversight.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registered after CORSMiddleware, not before the module-level constants/
# helpers below (SYSTEM_PROMPT_TEMPLATE, HUMAN_ESCALATION_MESSAGE,
# _build_context_block) -- whatsapp_webhook.py imports those from this
# module, so this import must come after they're defined. See
# whatsapp_webhook.py for what the real Twilio integration does and
# doesn't handle.

SYSTEM_PROMPT_TEMPLATE = """You are the FinBuddy WhatsApp Coach, helping gig-economy borrowers understand \
their credit score, why decisions were made, and FinBuddy's data/policy practices.

STRICT RULES -- follow these exactly, they are compliance requirements, not style preferences:
1. Answer ONLY using the CONTEXT below and the borrower's own credit score / factors (if given). \
Never use outside knowledge, even if you believe it is true.
2. If the CONTEXT does not clearly cover the question, say plainly that you do not have a verified \
answer and the borrower should contact FinBuddy support or a human coach. Never guess, and never \
state an unverified specific figure (a retention period, a percentage, a legal deadline, an amount) \
as settled fact.
3. If any CONTEXT chunk is marked NEEDS_LEGAL_VERIFICATION, say that figure/claim is not yet \
confirmed by Legal -- do not repeat it as fact even if it appears in the context.
4. Keep the tone warm, plain-language, and specific to the borrower's own situation when their \
credit score / factors are given below -- do not give a generic answer if a specific one is possible.
5. Never give financial or legal advice beyond what CONTEXT supports.

CONTEXT:
{context}

BORROWER'S CREDIT SCORE: {credit_score}
BORROWER'S TOP FACTORS: {shap_factors}
"""

HUMAN_ESCALATION_MESSAGE = (
    "I don't have a confident, verified answer to that from FinBuddy's policy and coaching "
    "material. Let me connect you with a human coach who can help directly."
)


class CoachRequest(BaseModel):
    user_query: str
    transcribed_intent: str = ""
    f001_credit_score: int | None = None
    f003_shap_top_3: list[str] = Field(default_factory=list)


class SourceMetadata(BaseModel):
    source_file: str
    doc_type: str
    similarity: float
    legal_signoff_status: str | None = None


class CoachResponse(BaseModel):
    answer: str
    escalate_to_human: bool
    low_confidence: bool
    sources: list[SourceMetadata]
    latency_ms: float


def _build_context_block(results: list[dict]) -> str:
    blocks = []
    for r in results:
        meta = r["metadata"]
        flag = f" [LEGAL STATUS: {meta.get('legal_signoff_status')}]" if meta.get("legal_signoff_status") == "NEEDS_LEGAL_VERIFICATION" else ""
        blocks.append(f"--- Source: {meta.get('source_file')}{flag} ---\n{r['content']}")
    return "\n\n".join(blocks)


def _to_source_metadata(results: list[dict]) -> list[SourceMetadata]:
    return [
        SourceMetadata(
            source_file=r["metadata"].get("source_file", "unknown"),
            doc_type=r["metadata"].get("doc_type", "unknown"),
            similarity=r["similarity"],
            legal_signoff_status=r["metadata"].get("legal_signoff_status"),
        )
        for r in results
    ]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/whatsapp-coach/respond", response_model=CoachResponse)
async def whatsapp_coach_respond(request: CoachRequest) -> CoachResponse:
    start = time.perf_counter()

    query_text = request.transcribed_intent.strip() or request.user_query.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Both user_query and transcribed_intent are empty")

    retrieval = await search_corpus(query_text, top_k=3)

    if retrieval["low_confidence"]:
        latency_ms = (time.perf_counter() - start) * 1000
        sources = _to_source_metadata(retrieval["results"])
        audit_log.append_record(
            "http_api", query_text, HUMAN_ESCALATION_MESSAGE, True, True,
            [s.model_dump() for s in sources], latency_ms,
        )
        return CoachResponse(
            answer=HUMAN_ESCALATION_MESSAGE,
            escalate_to_human=True,
            low_confidence=True,
            sources=sources,
            latency_ms=round(latency_ms, 2),
        )

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        context=_build_context_block(retrieval["results"]),
        credit_score=request.f001_credit_score if request.f001_credit_score is not None else "not provided",
        shap_factors=", ".join(request.f003_shap_top_3) if request.f003_shap_top_3 else "not provided",
    )

    try:
        answer = await llm_client.generate(system_prompt, query_text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {exc}") from exc

    latency_ms = (time.perf_counter() - start) * 1000
    sources = _to_source_metadata(retrieval["results"])
    audit_log.append_record(
        "http_api", query_text, answer, False, False,
        [s.model_dump() for s in sources], latency_ms,
    )
    return CoachResponse(
        answer=answer,
        escalate_to_human=False,
        low_confidence=False,
        sources=sources,
        latency_ms=round(latency_ms, 2),
    )


# Imported down here, not at the top of the file: whatsapp_webhook.py pulls
# SYSTEM_PROMPT_TEMPLATE / HUMAN_ESCALATION_MESSAGE / _build_context_block
# from this module, so this module must finish defining them first --
# importing at the top would be a real circular-import failure, not just
# style.
from rag_service.whatsapp_webhook import router as twilio_whatsapp_router  # noqa: E402

app.include_router(twilio_whatsapp_router)
