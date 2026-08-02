"""Tests for the Twilio WhatsApp webhook (rag_service/whatsapp_webhook.py).

Deliberately does NOT re-test retrieval/generation correctness -- that's
already covered end-to-end by tests/test_rag_pipeline.py against the same
underlying search_corpus/llm_client. What's actually new and worth testing
here is webhook-specific: valid TwiML shape, voice-note detection (since
transcription is deliberately unsupported, see whatsapp_webhook.py's
docstring), empty-body handling, and Twilio signature validation.

Run: pytest tests/test_whatsapp_webhook.py -v
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from rag_service.main import app

# No pool-cleanup fixture here, unlike test_rag_pipeline.py: TestClient runs
# each request against its own internal event loop (sync-over-async via
# httpx), which never lines up with pytest-asyncio's fixture loop, so
# reusing that file's `await close_pool()` pattern just trades a harmless
# leaked pool at process exit for a spurious "Event loop is closed" test
# failure. Confirmed by trying it.

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_token_by_default(monkeypatch):
    """Tests below assume TWILIO_AUTH_TOKEN is unset unless a test explicitly
    sets it -- don't rely on the real ambient environment/.env actually being
    empty, since rag_service/.env now has a real token for local testing
    against the live sandbox (llm_client.py's load_dotenv() picks it up).
    Each test gets a fresh, isolated "" baseline regardless of that."""
    monkeypatch.setattr("rag_service.whatsapp_webhook.TWILIO_AUTH_TOKEN", "")


def test_empty_body_asks_to_retype():
    resp = client.post(
        "/webhook/twilio/whatsapp",
        data={"From": "whatsapp:+919999999999", "Body": "", "NumMedia": "0"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert "<Message>" in resp.text
    assert "didn't catch a question" in resp.text


def test_voice_note_gets_transcription_unsupported_reply():
    """Confirms the honest fallback: a media message is detected and answered
    plainly, never silently mistranscribed or dropped."""
    resp = client.post(
        "/webhook/twilio/whatsapp",
        data={
            "From": "whatsapp:+919999999999",
            "Body": "",
            "NumMedia": "1",
            "MediaContentType0": "audio/ogg",
            "MediaUrl0": "https://api.twilio.com/fake/media/url",
        },
    )
    assert resp.status_code == 200
    assert "can't transcribe WhatsApp voice notes yet" in resp.text


def test_response_is_valid_twiml():
    resp = client.post(
        "/webhook/twilio/whatsapp",
        data={"From": "whatsapp:+919999999999", "Body": "", "NumMedia": "0"},
    )
    assert resp.text.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert resp.text.strip().endswith("</Response>")


def test_missing_signature_rejected_when_auth_token_configured(monkeypatch):
    """With TWILIO_AUTH_TOKEN set, an unsigned request must be rejected --
    this is the difference between a real deployment and local dev."""
    monkeypatch.setattr("rag_service.whatsapp_webhook.TWILIO_AUTH_TOKEN", "fake_token_for_test")
    resp = client.post(
        "/webhook/twilio/whatsapp",
        data={"From": "whatsapp:+919999999999", "Body": "hello", "NumMedia": "0"},
    )
    assert resp.status_code == 403


def test_valid_signature_accepted(monkeypatch):
    """Builds a real Twilio-style signature with the RequestValidator (the
    same algorithm Twilio itself uses) and confirms our validator accepts
    it -- proves the validation logic, not just that it's disabled."""
    fake_token = "fake_token_for_test"
    monkeypatch.setattr("rag_service.whatsapp_webhook.TWILIO_AUTH_TOKEN", fake_token)

    form = {"From": "whatsapp:+919999999999", "Body": "", "NumMedia": "0"}
    url = "http://testserver/webhook/twilio/whatsapp"
    signature = RequestValidator(fake_token).compute_signature(url, form)

    resp = client.post(
        "/webhook/twilio/whatsapp",
        data=form,
        headers={"X-Twilio-Signature": signature},
    )
    assert resp.status_code == 200


@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="No GROQ_API_KEY set")
def test_real_text_message_returns_grounded_answer():
    resp = client.post(
        "/webhook/twilio/whatsapp",
        data={
            "From": "whatsapp:+919999999999",
            "Body": "Why do you need my UPI transaction data?",
            "NumMedia": "0",
        },
    )
    assert resp.status_code == 200
    assert "<Message>" in resp.text
    if "having trouble generating an answer" in resp.text:
        # Same real, non-mocked rate-limit exhaustion test_rag_pipeline.py's
        # real-Groq tests already skip on -- the webhook's own graceful
        # fallback (see whatsapp_webhook.py) fired correctly; there's just
        # no live LLM quota left to assert real answer content against.
        pytest.skip("Groq daily token quota exhausted (429) -- webhook's fallback path fired correctly")
    assert "UPI" in resp.text or "transaction" in resp.text.lower()
