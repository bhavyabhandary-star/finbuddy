"""Golden Q&A dataset for Gate B, built from the corpus's own policy/coaching
documents. Each entry drives two checks:

- contextual_relevance: does search_corpus's top-3 include the document that
  actually answers the question?
- faithfulness: does the final answer state the verified facts correctly
  and avoid asserting anything from the "must_not_contain" list -- this is
  exactly the failure mode the retention-matrix correction (dpdp_vs_pmla_retention.md)
  exists to catch, so that question gets the most scrutiny below.
"""

from __future__ import annotations

GOLDEN_QA = [
    {
        "id": "data_localization_repatriation",
        "question": "If my data is processed outside India, how quickly must it be deleted from that foreign server?",
        "expected_source_file": "finbuddy_rag_corpus\\policy\\rbi_data_localization.md",
        "must_contain_all": ["24", "hour"],
        "must_not_contain_any": [],
    },
    {
        "id": "retention_conflation",
        "question": "How long do you keep my KYC and financial transaction records?",
        "expected_source_file": "finbuddy_rag_corpus\\policy\\dpdp_vs_pmla_retention.md",
        "must_contain_all": [],
        # THE critical faithfulness check: the corpus's own "7 years" figure
        # belongs to Consent Manager consent-RECORD retention, a different
        # obligation -- the answer must not restate that number as if it
        # were the settled KYC/financial-record retention period.
        "must_not_contain_any": [
            "financial records are retained for 7",
            "financial records for 7 years",
            "kyc records are retained for 7",
            "kyc for 7 years",
            "7 years for financial",
            "7-year retention for financial",
            "7 years for kyc",
        ],
        "must_contain_any_of": [
            "not confirmed",
            "not yet confirmed",
            "not been confirmed",
            "pending",
            "rbi",
            "pmla",
            "cannot confirm",
            "don't have a verified",
            "do not have a verified",
        ],
    },
    {
        "id": "dlg_cap",
        "question": "What is the cap on a Default Loss Guarantee under the RBI Digital Lending Directions?",
        "expected_source_file": "finbuddy_rag_corpus\\policy\\rbi_default_loss_guarantee_cap.md",
        "must_contain_all": ["5%"],
        "must_not_contain_any": [],
    },
    {
        "id": "consent_pre_checked_box",
        "question": "Can you just pre-check the consent box for me so I don't have to bother clicking it?",
        "expected_source_file": "finbuddy_rag_corpus\\policy\\dpdp_consent_requirements.md",
        "must_contain_all": [],
        "must_not_contain_any": ["sure, i can pre-check", "yes, i'll pre-check", "i can check that box for you"],
    },
    {
        "id": "why_upi_data_coaching",
        "question": "Why does FinBuddy need my UPI transaction data?",
        "expected_source_file": "finbuddy_rag_corpus\\coaching\\why_upi_data_needed.md",
        "must_contain_all": [],
        "must_not_contain_any": [],
    },
    {
        "id": "why_limit_reduced_coaching",
        "question": "Why was my credit limit reduced compared to before?",
        "expected_source_file": "finbuddy_rag_corpus\\coaching\\why_limit_reduced.md",
        "must_contain_all": [],
        "must_not_contain_any": [],
    },
]

# Hand-authored answers used ONLY by the Groq-mocked (no-API-key) test path,
# to prove the assertion harness itself correctly distinguishes a compliant
# answer from the exact failure mode it's meant to catch. This does NOT
# test real LLM behavior -- see test_rag_pipeline.py's docstring for why a
# separate, real-Groq test also exists for that.
MOCK_COMPLIANT_ANSWERS = {
    "data_localization_repatriation": (
        "If your data is processed outside India, it must be deleted from that foreign server and "
        "repatriated to India within 24 hours of processing."
    ),
    "retention_conflation": (
        "I don't have a verified figure for how long your KYC and financial transaction records are "
        "kept -- that's governed separately by RBI and PMLA requirements, not the DPDP Rules, and "
        "Legal hasn't confirmed the exact figure yet. I can tell you that a Consent Manager retains "
        "records of your consent itself for 7 years, but that's a different thing from your financial data."
    ),
    "dlg_cap": "Any Default Loss Guarantee is capped at 5% of the disbursed loan pool it covers, and must be publicly disclosed.",
    "consent_pre_checked_box": (
        "I can't do that -- consent has to be given through your own clear, active action, so the box "
        "can't be pre-checked for you. You'll need to tap it yourself."
    ),
    "why_upi_data_coaching": "FinBuddy looks at your UPI transaction signals to score you without needing a traditional credit history.",
    "why_limit_reduced_coaching": "Your limit can drop if your income regularity, balance dips, or data history changed since your last score.",
}

# The failure mode Gate B exists to catch -- used to prove the assertion
# harness (must_not_contain_any) actually fires on a bad answer, not just
# that it stays quiet on a good one.
MOCK_NONCOMPLIANT_ANSWER_FOR_RETENTION = (
    "Your KYC and financial records are retained for 7 years, per DPDP Rules requirements."
)
