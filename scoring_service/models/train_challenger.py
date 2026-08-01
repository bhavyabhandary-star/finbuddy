"""Trains a genuinely different second F-001 model to act as a "challenger"
for canary.py -- routing traffic between two copies of the SAME model would
make the champion/challenger demo meaningless. Different hyperparameters
(deeper trees, more rounds) so the comparison in canary.py is real.

Run: python -m scoring_service.models.train_challenger
"""

from __future__ import annotations

import json
from pathlib import Path

import xgboost as xgb
from joblib import dump
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score

from scoring_service.features.feature_engineering import (
    LABEL_COLUMN,
    RANDOM_STATE,
    UPI_SIGNAL_COLUMNS,
    split_main_dataset,
)
from scoring_service.models.train_credit_score import AUC_TARGET

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"


def train() -> dict:
    train_df, test_df = split_main_dataset()
    X_train, y_train = train_df[UPI_SIGNAL_COLUMNS], train_df[LABEL_COLUMN]
    X_test, y_test = test_df[UPI_SIGNAL_COLUMNS], test_df[LABEL_COLUMN]

    # Deliberately different from F-001's champion hyperparameters (deeper,
    # more rounds, lower learning rate) -- a real alternative candidate, not
    # a clone.
    challenger_base = xgb.XGBClassifier(
        n_estimators=350,
        max_depth=5,
        learning_rate=0.04,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=RANDOM_STATE,
    )
    calibrated = CalibratedClassifierCV(challenger_base, method="isotonic", cv=5)
    calibrated.fit(X_train, y_train)

    probs = calibrated.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, probs)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    dump(calibrated, ARTIFACTS_DIR / "f001_challenger_calibrated.joblib")

    metrics = {
        "model": "F-001 challenger (XGBoost, deeper/slower variant, isotonic-calibrated)",
        "hyperparameters": {"n_estimators": 350, "max_depth": 5, "learning_rate": 0.04},
        "auc_target": AUC_TARGET,
        "auc_holdout": round(float(auc), 4),
        "gate_pass": bool(auc >= AUC_TARGET),
    }
    with open(ARTIFACTS_DIR / "f001_challenger_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    return metrics


if __name__ == "__main__":
    result = train()
    print(json.dumps(result, indent=2))
