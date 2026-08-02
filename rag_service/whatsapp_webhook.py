"""POST /webhook/twilio/whatsapp -- receives inbound WhatsApp messages via
Twilio and replies with a RAG-grounded coach answer, using the same
retrieval + Groq generation pipeline as /api/v1/whatsapp-coach/respond.

WHAT THIS DOES AND DOESN'T HANDLE, HONESTLY:

- Text messages: fully supported, routed straight into the coach pipeline.
- Voice notes: WhatsApp/Twilio delivers these as Opus-in-OGG
  (`audio/ogg; codec=opus`). scoring_service/voice/asr.py's transcribe()
  only reads plain 16-bit PCM WAV via the stdlib `wave` module (deliberately,
  to avoid librosa/numba -- see that module's docstring) -- it cannot decode
  OGG/Opus without an external decoder (ffmpeg), which isn't installed on
  this dev machine (confirmed: `where ffmpeg` found nothing). So voice notes
  are detected and answered with a plain "please type your question instead"
  reply rather than silently failing or mistranscribing -- the ASR/intent
  pipeline itself is real and tested (see scoring_service/voice/), just not
  wired to this codec yet. Adding ffmpeg (or an OGG/Opus-capable decoder) to
  the deployment is the real fix, not attempted here.
- No per-user profile lookup: there's no phone-number -> scored-borrower-
  profile store in this project, so every reply uses the general (non-
  personalized) coach path (f001_credit_score / shap factors both "not
  provided"). Wiring a real user would mean looking up their last F-001
  score by phone number, which needs a user/session store this project
  doesn't have.
- Signature validation: verifies X-Twilio-Signature against
  TWILIO_AUTH_TOKEN per Twilio's documented HMAC scheme, using the
  request's real public URL (respecting X-Forwarded-Proto, since real
  deployments -- including HF Spaces -- terminate TLS in front of the app,
  so request.url.scheme alone would be wrong). If TWILIO_AUTH_TOKEN isn't
  set, validation is skipped with a loud warning -- fine for local dev,
  never acceptable for a real deployed webhook Twilio actually calls.

Twilio's webhook timeout (15s) comfortably covers this project's measured
coach latency (p95 ~5s, see main.py's docstring), so this replies
synchronously with TwiML rather than needing an async reply via Twilio's
separate REST send-message API.
"""

from __future__ import annotations

import logging
import os
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from rag_service import audit_log, llm_client
from rag_service.main import HUMAN_ESCALATION_MESSAGE, SYSTEM_PROMPT_TEMPLATE, _build_context_block, _to_source_metadata
from rag_service.retriever import search_corpus

logger = logging.getLogger(__name__)

router = APIRouter()

TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")

VOICE_NOTE_REPLY = (
    "I got your voice note, but I can't transcribe WhatsApp voice notes yet "
    "(that needs an audio decoder this deployment doesn't have installed). "
    "Could you type your question instead?"
)


def _public_url(request: Request) -> str:
    """Reconstructs the URL exactly as Twilio saw it, for signature
    validation -- respects X-Forwarded-Proto since TLS is terminated in
    front of the app in every real deployment of this service."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    return f"{scheme}://{request.url.netloc}{request.url.path}"


async def _validate_twilio_request(request: Request, form: dict) -> None:
    if not TWILIO_AUTH_TOKEN:
        logger.warning(
            "TWILIO_AUTH_TOKEN not set -- skipping Twilio signature validation. "
            "Fine for local dev, NEVER acceptable for a real deployed webhook."
        )
        return
    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    signature = request.headers.get("x-twilio-signature", "")
    if not validator.validate(_public_url(request), form, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")


@router.post("/webhook/twilio/whatsapp")
async def twilio_whatsapp_webhook(request: Request) -> Response:
    form = dict(await request.form())
    await _validate_twilio_request(request, form)

    from_number = form.get("From", "unknown")
    body = (form.get("Body") or "").strip()
    num_media = int(form.get("NumMedia", "0") or "0")

    twiml = MessagingResponse()

    if num_media > 0:
        content_type = form.get("MediaContentType0", "")
        logger.info(f"Voice/media message from {from_number}: {content_type} (not transcribed, see module docstring)")
        twiml.message(VOICE_NOTE_REPLY)
        return Response(content=str(twiml), media_type="application/xml")

    if not body:
        twiml.message("I didn't catch a question there -- could you type it again?")
        return Response(content=str(twiml), media_type="application/xml")

    start = time.perf_counter()
    retrieval = await search_corpus(body, top_k=3)
    sources = [s.model_dump() for s in _to_source_metadata(retrieval["results"])]

    if retrieval["low_confidence"]:
        latency_ms = (time.perf_counter() - start) * 1000
        audit_log.append_record("whatsapp", body, HUMAN_ESCALATION_MESSAGE, True, True, sources, latency_ms)
        twiml.message(HUMAN_ESCALATION_MESSAGE)
        return Response(content=str(twiml), media_type="application/xml")

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        context=_build_context_block(retrieval["results"]),
        credit_score="not provided",
        shap_factors="not provided",
    )

    try:
        answer = await llm_client.generate(system_prompt, body)
    except Exception:
        logger.exception(f"LLM generation failed for WhatsApp message from {from_number}")
        twiml.message("Sorry, I'm having trouble generating an answer right now -- please try again in a moment.")
        return Response(content=str(twiml), media_type="application/xml")

    latency_ms = (time.perf_counter() - start) * 1000
    audit_log.append_record("whatsapp", body, answer, False, False, sources, latency_ms)
    twiml.message(answer)
    return Response(content=str(twiml), media_type="application/xml")
