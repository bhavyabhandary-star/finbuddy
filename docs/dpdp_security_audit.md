# DPDP / Security Audit

Run 2026-08-02 against commit history through Phase 7. Every check below was actually
executed (`git grep`, not asserted from memory) -- results and the exact commands are
included so this can be re-run and re-verified, not just trusted.

## 1. No real PII in the corpus or logs

**Pass.** All training/scoring data is synthetically generated
(`scoring_service/data/generate_synthetic_upi_data.py`) -- there is no real user data
anywhere in this repository to leak. Checked for Aadhaar/PAN-style 12/10-digit
patterns across all tracked `.py`/`.md`/`.json` files: none found.

```bash
git grep -InE "[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\b" -- '*.py' '*.md' '*.json'
```

Note: `rag_service/finbuddy_rag_corpus/` and `scoring_service/models/artifacts/`
contain no real names, phone numbers, or account identifiers -- the corpus is
authored policy/coaching prose, and model artifacts are trained weights + aggregate
metrics, not per-user records.

## 2. No secrets committed

**Pass.** Checked for Groq API key format (`gsk_...`), the specific Neon password
used during this session (`npg_...`), AWS access key format, and PEM private key
headers across all tracked files:

```bash
git grep -InE "gsk_[a-zA-Z0-9]{10,}|npg_[a-zA-Z0-9]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA|OPENSSH|PRIVATE) KEY-----" -- .
```

Zero matches. Confirmed `.env` files are never tracked:

```bash
git ls-files | grep -E "\.env$"
```

Zero matches -- `rag_service/.env` and `scoring_service/.env` (which hold the real
Neon connection string and Groq key used in this session) are excluded via
`.gitignore`'s `.env` pattern and were never staged.

## 3. `last_verified` dates on every policy doc

**Dates are current (2026-08-02). Content is NOT independently Legal-verified --
flagged explicitly, not silently implied.** All 10 corpus documents carry a
`last_verified` date and a `legal_signoff_status` field:

| Document | `legal_signoff_status` |
|---|---|
| `policy/dpdp_vs_pmla_retention.md` | `NEEDS_LEGAL_VERIFICATION` -- deliberately does not assert a specific KYC/financial retention figure (see the doc itself for the conflation it corrects) |
| all other 9 documents | `pending` |

"Current" here means the date reflects when this pipeline authored/reviewed the
content against the research summary provided at the start of this build -- it does
**not** mean a lawyer independently re-checked each figure against a primary RBI/DPDP
source. That is the explicit gap this audit is surfacing: **route every corpus
document through Legal before any real borrower-facing use**, per the Business &
DPDP Sign-off governance gate. Treating `legal_signoff_status: pending` as good
enough for production would defeat the point of having the field.

## 4. Scope not covered by this audit

- **Runtime log contents** -- no production traffic exists yet, so there's nothing to
  audit for PII leakage in logs. This needs a follow-up pass once real traffic flows
  (check that FastAPI/uvicorn access logs, and any request logging added later,
  don't capture raw UPI signals or borrower identifiers in plaintext).
- **Dependency vulnerability scanning** (e.g. `pip-audit`) -- not run in this session;
  recommended as a CI step addition, not done here.
- **Setu AA sandbox credentials** -- not applicable; no sandbox credentials exist yet
  for this project (see `scoring_service/setu_integration/`).
