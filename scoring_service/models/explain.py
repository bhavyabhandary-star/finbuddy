"""F-003: top-3 plain-language SHAP factors per decision, target <500ms.

Uses XGBoost's native Tree SHAP (Booster.predict(pred_contribs=True)) --
see requirements.txt for why the `shap` package isn't used on this machine.
The contribution values this produces ARE Tree SHAP values (same additive,
game-theoretic guarantee: sum(contributions) + bias == raw model margin),
just computed by XGBoost's own C++ implementation instead of the `shap`
package's Python wrapper around the same algorithm.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from scoring_service.features.feature_engineering import UPI_SIGNAL_COLUMNS

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
LATENCY_TARGET_MS = 500

# One plain-language template per signal, worded for both directions. These
# are shown to a borrower over WhatsApp, so they stay concrete and actionable
# rather than statistical.
FACTOR_TEMPLATES = {
    "avg_monthly_income": {
        "positive": "Your average monthly UPI income of Rs {value:,.0f} supports a higher limit.",
        "negative": "Your average monthly UPI income of Rs {value:,.0f} is on the lower side for this request.",
        "action": "Linking more income sources (a second gig platform, business UPI ID) can raise this over time.",
    },
    "income_regularity_score": {
        "positive": "Your income arrives on a regular monthly pattern, which lenders read as stability.",
        "negative": "Your income varies a lot month to month, which reads as higher risk to lenders.",
        "action": "Try to keep at least one predictable income credit landing on the same days each month.",
    },
    "tx_count_30d": {
        "positive": "You have {value:.0f} UPI transactions in the last 30 days -- an active, well-used account.",
        "negative": "Only {value:.0f} UPI transactions in the last 30 days makes your activity harder to verify.",
        "action": "Route more of your day-to-day payments through this UPI account.",
    },
    "merchant_diversity": {
        "positive": "You transact with {value:.0f} different merchants/counterparties, showing a broad financial footprint.",
        "negative": "You transact with only {value:.0f} different merchants, which limits how much we can verify.",
        "action": "Diversify where your income and spending flow through UPI.",
    },
    "balance_dip_frequency": {
        "positive": "Your account balance rarely runs critically low.",
        "negative": "Your balance dropped very low {value:.0f} times recently, a sign of cash-flow stress.",
        "action": "Building even a small buffer (Rs 500-1000) reduces this risk signal.",
    },
    "b2b_ratio": {
        "positive": "A meaningful share of your inflow looks like business/B2B receipts, which reads as stable revenue.",
        "negative": "Little of your inflow looks like business receipts -- mostly consumer-style payments.",
        "action": "If you run a business, request digital (UPI/bank) receipts from suppliers/customers instead of cash.",
    },
    "avg_transaction_size": {
        "positive": "Your typical transaction size of Rs {value:,.0f} is consistent with steady income flow.",
        "negative": "Your typical transaction size of Rs {value:,.0f} is unusually small or large for this pattern.",
        "action": "No specific action -- this factor carries less weight than income and regularity.",
    },
    "tenure_months": {
        "positive": "You've shared {value:.0f} months of UPI history, giving us a fuller picture.",
        "negative": "Only {value:.0f} months of UPI history is available, limiting confidence.",
        "action": "Consenting to a longer Account Aggregator data-sharing window improves this.",
    },
}


def load_raw_booster() -> xgb.XGBClassifier:
    model = xgb.XGBClassifier()
    model.load_model(str(ARTIFACTS_DIR / "f001_xgboost_raw.json"))
    return model


def compute_contributions(model: xgb.XGBClassifier, X: pd.DataFrame) -> np.ndarray:
    """Returns (n_rows, n_features + 1) -- last column is the bias term.
    contributions.sum(axis=1) == raw margin (pre-sigmoid) for each row.
    """
    dmatrix = xgb.DMatrix(X, feature_names=list(X.columns))
    return model.get_booster().predict(dmatrix, pred_contribs=True)


def top3_plain_language(row: pd.Series, contributions: np.ndarray) -> list[dict]:
    """contributions: 1D array of length len(UPI_SIGNAL_COLUMNS) + 1 (bias last)."""
    feature_contribs = list(zip(UPI_SIGNAL_COLUMNS, contributions[:-1]))
    feature_contribs.sort(key=lambda x: abs(x[1]), reverse=True)

    factors = []
    for feature_name, contrib in feature_contribs[:3]:
        direction = "positive" if contrib >= 0 else "negative"
        template = FACTOR_TEMPLATES[feature_name]
        factors.append(
            {
                "factor": feature_name,
                "shap_contribution": round(float(contrib), 4),
                "direction": direction,
                "plain_english": template[direction].format(value=row[feature_name]),
                "action": template["action"],
            }
        )
    return factors


def explain_batch(X: pd.DataFrame) -> list[list[dict]]:
    model = load_raw_booster()
    contributions = compute_contributions(model, X)
    return [top3_plain_language(X.iloc[i], contributions[i]) for i in range(len(X))]


def _latency_benchmark(n_rows: int = 1) -> float:
    """Returns ms for one explain call (retrieval-equivalent path for F-003 alone,
    not the combined RAG p95 budget -- that's measured separately in Phase 6)."""
    model = load_raw_booster()
    rng = np.random.default_rng(0)
    sample = pd.DataFrame(
        {
            "avg_monthly_income": rng.uniform(5000, 80000, n_rows),
            "income_regularity_score": rng.uniform(0.1, 0.95, n_rows),
            "tx_count_30d": rng.integers(10, 500, n_rows),
            "merchant_diversity": rng.integers(1, 50, n_rows),
            "balance_dip_frequency": rng.integers(0, 10, n_rows),
            "b2b_ratio": rng.uniform(0, 1, n_rows),
            "avg_transaction_size": rng.uniform(50, 5000, n_rows),
            "tenure_months": rng.integers(1, 13, n_rows),
        }
    )[UPI_SIGNAL_COLUMNS]

    start = time.perf_counter()
    explain_batch(sample)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms


if __name__ == "__main__":
    ms = _latency_benchmark(n_rows=1)
    print(f"Single-row explain latency: {ms:.2f}ms (target <{LATENCY_TARGET_MS}ms)")
    status = "PASS" if ms < LATENCY_TARGET_MS else "FAIL"
    print(f"F-003 latency gate: {status}")

    model = load_raw_booster()
    rng = np.random.default_rng(1)
    sample = pd.DataFrame(
        {
            "avg_monthly_income": [21000.0],
            "income_regularity_score": [0.81],
            "tx_count_30d": [340],
            "merchant_diversity": [11],
            "balance_dip_frequency": [3],
            "b2b_ratio": [0.12],
            "avg_transaction_size": [95.0],
            "tenure_months": [6],
        }
    )[UPI_SIGNAL_COLUMNS]
    print("\nExample top-3 factors for a sample profile:")
    for f in explain_batch(sample)[0]:
        print(f"  [{f['direction']}] {f['factor']}: {f['plain_english']}")
