"""Gate B: RAG quality tests, golden-Q&A-driven.

Two layers, deliberately different in what they prove:

1. Contextual relevance (test_contextual_relevance_*): runs the REAL
   retriever against the REAL Neon database. No LLM involved. Proves
   search_corpus actually finds the right document for each golden
   question -- e.g. a question about offshore data processing retrieves
   the data-localization/24-hour-repatriation chunk, not an unrelated one.

2. Faithfulness (test_faithfulness_*): two sub-paths, both real assertions,
   proving different things:
   - test_faithfulness_mock_harness_*: monkeypatches llm_client.generate
     with hand-authored answers (see golden_qa.py). This does NOT test real
     LLM behavior -- it proves the assertion harness itself correctly
     distinguishes a compliant answer from the exact retention-conflation
     failure mode this corpus correction exists to catch. Runs with no
     GROQ_API_KEY needed, so it's always part of CI.
   - test_faithfulness_real_groq_*: calls the ACTUAL Groq API and applies
     the same assertions to a real model's real answer. Skipped
     automatically if GROQ_API_KEY isn't set (e.g. a contributor's machine
     without a key) -- runs whenever a key is available, including via
     GitHub Secrets in CI per the deploy workflow.

Run: pytest tests/test_rag_pipeline.py -v
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

from rag_service import llm_client
from rag_service.main import CoachRequest, whatsapp_coach_respond
from rag_service.retriever import close_pool, search_corpus
from tests.golden_qa import GOLDEN_QA, MOCK_COMPLIANT_ANSWERS, MOCK_NONCOMPLIANT_ANSWER_FOR_RETENTION

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True, scope="module")
async def _cleanup_pool():
    yield
    await close_pool()


@pytest.mark.parametrize("case", GOLDEN_QA, ids=[c["id"] for c in GOLDEN_QA])
async def test_contextual_relevance(case):
    result = await search_corpus(case["question"], top_k=3)
    retrieved_files = [r["metadata"]["source_file"] for r in result["results"]]
    assert case["expected_source_file"] in retrieved_files, (
        f"Expected {case['expected_source_file']} in top-3 for '{case['question']}', got {retrieved_files}"
    )
    assert not result["low_confidence"], (
        f"'{case['question']}' triggered low_confidence -- top similarity was too low even though "
        f"this question should be answerable from the corpus"
    )


def _check_assertions(case: dict, answer: str) -> None:
    answer_lower = answer.lower()
    for required in case["must_contain_all"]:
        assert required.lower() in answer_lower, f"[{case['id']}] answer missing required text '{required}': {answer!r}"
    for forbidden in case["must_not_contain_any"]:
        assert forbidden.lower() not in answer_lower, f"[{case['id']}] answer contains forbidden text '{forbidden}': {answer!r}"
    if "must_contain_any_of" in case:
        assert any(alt.lower() in answer_lower for alt in case["must_contain_any_of"]), (
            f"[{case['id']}] answer contains none of the expected alternatives "
            f"{case['must_contain_any_of']}: {answer!r}"
        )


@pytest.mark.parametrize("case", GOLDEN_QA, ids=[c["id"] for c in GOLDEN_QA])
async def test_faithfulness_mock_harness_recognizes_compliant_answer(case, monkeypatch):
    """Proves the assertion harness correctly PASSES a compliant answer."""
    mock_answer = MOCK_COMPLIANT_ANSWERS[case["id"]]

    async def fake_generate(system_prompt: str, user_prompt: str) -> str:
        return mock_answer

    monkeypatch.setattr(llm_client, "generate", fake_generate)

    request = CoachRequest(user_query=case["question"], f003_shap_top_3=[])
    response = await whatsapp_coach_respond(request)

    assert not response.escalate_to_human, f"[{case['id']}] unexpectedly escalated instead of answering"
    _check_assertions(case, response.answer)


async def test_faithfulness_mock_harness_catches_retention_conflation(monkeypatch):
    """Proves the assertion harness correctly FAILS the exact bad answer
    the retention-matrix correction exists to prevent -- if this test
    doesn't fail when it should, the harness itself is broken."""
    case = next(c for c in GOLDEN_QA if c["id"] == "retention_conflation")

    async def fake_generate_bad_answer(system_prompt: str, user_prompt: str) -> str:
        return MOCK_NONCOMPLIANT_ANSWER_FOR_RETENTION

    monkeypatch.setattr(llm_client, "generate", fake_generate_bad_answer)

    request = CoachRequest(user_query=case["question"], f003_shap_top_3=[])
    response = await whatsapp_coach_respond(request)

    with pytest.raises(AssertionError, match="forbidden text"):
        _check_assertions(case, response.answer)


@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="GROQ_API_KEY not set -- skipping real-model faithfulness test")
@pytest.mark.parametrize("case", GOLDEN_QA, ids=[c["id"] for c in GOLDEN_QA])
async def test_faithfulness_real_groq(case):
    """Calls the actual Groq API. This is the test that validates real
    model behavior, not just the assertion harness."""
    request = CoachRequest(
        user_query=case["question"],
        f001_credit_score=720,
        f003_shap_top_3=["income_regularity_score: +", "balance_dip_frequency: -"],
    )
    response = await whatsapp_coach_respond(request)

    assert not response.escalate_to_human, f"[{case['id']}] unexpectedly escalated: {response.answer}"
    _check_assertions(case, response.answer)


async def test_low_confidence_escalation_fires_on_off_corpus_query():
    """End-to-end: a genuinely off-corpus query must escalate, not hallucinate an answer."""
    request = CoachRequest(user_query="what is the weather like today", f003_shap_top_3=[])
    response = await whatsapp_coach_respond(request)

    assert response.escalate_to_human is True
    assert response.low_confidence is True
    assert "human coach" in response.answer.lower()
