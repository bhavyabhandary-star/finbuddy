"""Real-time scoring endpoint: F-006 anomaly pre-check -> F-001 calibrated
score -> F-003 top-3 SHAP factors -> F-012 fairness-aware approval decision.

Called synchronously by the PWA dashboard and the WhatsApp coach (which
also needs f001_credit_score + f003_shap_top_3 for its own /whatsapp-coach
request, per the RAG service's API contract in Phase 6).

Run: uvicorn scoring_service.api.main:app --reload --port 8001
Docs: http://localhost:8001/docs
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from scoring_service.api import audit_log
from scoring_service.api.scoring_engine import Geography, ScoringEngine
from scoring_service.voice.asr import transcribe as asr_transcribe
from scoring_service.voice.intent_classifier import predict_intent

app = FastAPI(
    title="FinBuddy Scoring Service",
    description="F-001/F-003/F-006/F-012 real-time credit scoring for gig-economy UPI profiles.",
    version="0.1.0",
)

# Wide open (*) is a deliberate demo-grade choice, not an oversight: this API
# has no auth/cookies/session state, every response is either public-corpus-
# grounded or a synthetic-data-trained score, so cross-origin access doesn't
# expose anything sensitive. A real production deployment behind real
# borrower auth would scope this to the actual frontend's origin instead.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Loaded once at process start, not per-request -- this is what keeps p95 well
# under the 500ms budget (model loading itself takes ~1-2s, scoring a
# request does not).
engine = ScoringEngine()


class ScoreRequest(BaseModel):
    avg_monthly_income: float = Field(..., gt=0, description="Mean monthly UPI credit volume, INR")
    income_regularity_score: float = Field(..., ge=0, le=1)
    tx_count_30d: int = Field(..., ge=0)
    merchant_diversity: int = Field(..., ge=0)
    balance_dip_frequency: int = Field(..., ge=0)
    b2b_ratio: float = Field(..., ge=0, le=1)
    avg_transaction_size: float = Field(..., gt=0)
    tenure_months: int = Field(..., ge=1, le=12)
    geography: Geography | None = Field(
        None,
        description=(
            "Optional. Without it, the fairness-mitigated approval decision "
            "(F-012) can't be applied and the response falls back to a plain "
            "probability threshold -- see fairness_mitigation_applied in the response."
        ),
    )
    user_id: str | None = None


class ScoreFactor(BaseModel):
    factor: str
    shap_contribution: float
    direction: str
    plain_english: str
    action: str


class ScoreResponse(BaseModel):
    user_id: str | None
    credit_score: int
    calibrated_probability_of_repayment: float
    approved: bool
    fairness_mitigation_applied: bool
    income_band: str
    is_anomalous: bool
    anomaly_note: str | None
    top_3_factors: list[ScoreFactor]
    latency_ms: float


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/score", response_model=ScoreResponse)
def score(request: ScoreRequest) -> ScoreResponse:
    start = time.perf_counter()
    signals = request.model_dump(exclude={"geography", "user_id"})

    try:
        result = engine.score(signals, geography=request.geography)
    except Exception as exc:  # noqa: BLE001 -- surface as a clean 500, not a stack trace to the caller
        raise HTTPException(status_code=500, detail=f"Scoring failed: {exc}") from exc

    latency_ms = (time.perf_counter() - start) * 1000
    audit_log.append_record("/api/v1/score", signals, result, latency_ms)
    return ScoreResponse(user_id=request.user_id, latency_ms=round(latency_ms, 2), **result)


class IntentRequest(BaseModel):
    text: str


@app.post("/api/v1/intent")
def intent(request: IntentRequest) -> dict:
    """F-007/9 intent classification on already-transcribed/typed text.
    First call is slow (loads LaBSE + classifier); subsequent calls are fast."""
    return predict_intent(request.text)


@app.post("/api/v1/voice-intent")
async def voice_intent(file: UploadFile, language: str | None = None):
    """F-007/9 full path: audio (16-bit PCM WAV) -> Whisper transcription ->
    intent classification. See voice/asr.py for the honest caveat on
    transcription quality not being validated against real Hindi/Tamil
    speech in this session -- only that the pipeline runs end to end.

    LATENCY CAVEAT: unlike F-001 scoring (<100ms, well within the 500ms
    real-time budget), Whisper-small on CPU is NOT real-time -- expect
    multiple seconds per voice note on this machine, not sub-second. This
    endpoint is designed for the WhatsApp coaching flow (async, user
    already expects a reply delay) not the onboarding-time synchronous
    scoring path. Production would need GPU inference or a smaller model
    (whisper-tiny) if sub-second voice response is actually required.
    """
    if language not in (None, "hindi", "tamil", "english"):
        raise HTTPException(status_code=400, detail="language must be one of hindi, tamil, english, or omitted")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        transcription = asr_transcribe(tmp_path, language=language)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Transcription failed: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    intent_result = predict_intent(transcription["text"])
    return {"transcription": transcription, **intent_result}
