"""F-006: Isolation Forest anomaly pre-check on the 8 UPI signals.

Unsupervised by design -- it never sees `is_anomalous` or `repaid_on_time`
at fit time, exactly as it will run pre-scoring on unlabeled new profiles
in production. `is_anomalous` (injected by the synthetic generator) exists
ONLY so this script can report an honest precision/recall against known
ground truth; F-006 itself has no access to it.

Run: python -m scoring_service.models.train_anomaly
"""

from __future__ import annotations

import json
from pathlib import Path

from joblib import dump
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score

from scoring_service.features.feature_engineering import (
    ANOMALY_COLUMN,
    RANDOM_STATE,
    UPI_SIGNAL_COLUMNS,
    split_main_dataset,
)

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
CONTAMINATION = 0.03  # matches ANOMALY_FRACTION in the synthetic generator


def train() -> dict:
    train_df, test_df = split_main_dataset()

    X_train = train_df[UPI_SIGNAL_COLUMNS]
    X_test, y_test_true_anomaly = test_df[UPI_SIGNAL_COLUMNS], test_df[ANOMALY_COLUMN]

    model = IsolationForest(
        n_estimators=200,
        contamination=CONTAMINATION,
        random_state=RANDOM_STATE,
    )
    model.fit(X_train)  # unsupervised: no labels passed

    # IsolationForest.predict: -1 = anomaly, 1 = normal
    raw_pred = model.predict(X_test)
    pred_is_anomalous = raw_pred == -1

    precision = precision_score(y_test_true_anomaly, pred_is_anomalous, zero_division=0)
    recall = recall_score(y_test_true_anomaly, pred_is_anomalous, zero_division=0)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    dump(model, ARTIFACTS_DIR / "f006_isolation_forest.joblib")

    metrics = {
        "model": "F-006 anomaly detection (Isolation Forest, unsupervised)",
        "contamination_param": CONTAMINATION,
        "precision_vs_synthetic_ground_truth": round(float(precision), 4),
        "recall_vs_synthetic_ground_truth": round(float(recall), 4),
        "n_test": len(test_df),
        "n_true_anomalies_in_test": int(y_test_true_anomaly.sum()),
        "n_flagged_in_test": int(pred_is_anomalous.sum()),
        "caveat": (
            "No governance-gate threshold is defined for F-006 in the spec "
            "(unlike F-001/Risk-Trend/F-012); these precision/recall numbers "
            "are reported for transparency against synthetic injected "
            "anomalies, not a pass/fail gate. Real deployment should expect "
            "lower precision against real, more diverse anomalous patterns."
        ),
    }
    with open(ARTIFACTS_DIR / "f006_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    return metrics


if __name__ == "__main__":
    result = train()
    print(json.dumps(result, indent=2))
