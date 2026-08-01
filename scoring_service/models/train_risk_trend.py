"""Featured: Risk-Trend classifier (Logistic Regression, Ridge). Target: held-out ROC-AUC >= 0.96.

Trains on the delta (late-window minus early-window) of each of the 8 UPI
signals, predicting whether a user's financial trend is improving (1) or
decaying (0). See generate_synthetic_upi_data.generate_risk_trend_dataset
for how the two windows and trend label are constructed.

Run: python -m scoring_service.models.train_risk_trend
"""

from __future__ import annotations

import json
from pathlib import Path

from joblib import dump
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from scoring_service.features.feature_engineering import RANDOM_STATE, split_risk_trend_dataset

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
ROC_AUC_TARGET = 0.96

DELTA_FEATURE_COLUMNS = [
    "delta_avg_monthly_income",
    "delta_income_regularity_score",
    "delta_tx_count_30d",
    "delta_merchant_diversity",
    "delta_balance_dip_frequency",
    "delta_b2b_ratio",
    "delta_avg_transaction_size",
    "delta_tenure_months",
]


def train() -> dict:
    train_df, test_df = split_risk_trend_dataset()

    X_train, y_train = train_df[DELTA_FEATURE_COLUMNS], train_df["trend_label"]
    X_test, y_test = test_df[DELTA_FEATURE_COLUMNS], test_df["trend_label"]

    # Ridge (L2) per the spec's "Logistic Regression (Ridge/Lasso)" note.
    # l1_ratio=0.0 is sklearn's current spelling of pure L2 (penalty= is deprecated).
    model = LogisticRegression(l1_ratio=0.0, C=1.0, max_iter=2000, random_state=RANDOM_STATE)
    model.fit(X_train, y_train)

    test_probs = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, test_probs)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    dump(model, ARTIFACTS_DIR / "risk_trend_logreg.joblib")

    metrics = {
        "model": "Risk-Trend classifier (Logistic Regression, Ridge/L2)",
        "roc_auc_target": ROC_AUC_TARGET,
        "roc_auc_holdout": round(float(auc), 4),
        "gate_pass": bool(auc >= ROC_AUC_TARGET),
        "n_train": len(train_df),
        "n_test": len(test_df),
        "features": DELTA_FEATURE_COLUMNS,
        "caveat": "Synthetic delta-window data; trend windows are generator-controlled, not observed real behavior.",
    }
    with open(ARTIFACTS_DIR / "risk_trend_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    return metrics


if __name__ == "__main__":
    result = train()
    print(json.dumps(result, indent=2))
    status = "PASS" if result["gate_pass"] else "FAIL"
    print(f"\nGate A (Risk-Trend ROC-AUC >= {ROC_AUC_TARGET}): {status} (got {result['roc_auc_holdout']})")
