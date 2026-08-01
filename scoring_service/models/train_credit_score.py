"""F-001: XGBoost credit-score model. Target: held-out AUC >= 0.82.

Trains on the 8 UPI signals only -- protected attributes are never model
features (F-012's fairness audit checks predictions against them
afterward, which is the correct pattern: don't feed protected attributes
in, then verify the *proxy* effect through the real features stays within
bounds).

Saves:
  models/artifacts/f001_xgboost_calibrated.joblib  -- calibrated classifier
  models/artifacts/f001_metrics.json                -- honest eval numbers

Run: python -m scoring_service.models.train_credit_score
"""

from __future__ import annotations

import json
from pathlib import Path

import xgboost as xgb
from joblib import dump
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss, roc_auc_score

from scoring_service.features.feature_engineering import (
    LABEL_COLUMN,
    RANDOM_STATE,
    UPI_SIGNAL_COLUMNS,
    split_main_dataset,
)

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
AUC_TARGET = 0.82


def prob_to_score(prob_good: float) -> int:
    """Map a calibrated P(repay) to the product's 300-850 band."""
    return int(round(300 + prob_good * 550))


def train() -> dict:
    train_df, test_df = split_main_dataset()

    X_train, y_train = train_df[UPI_SIGNAL_COLUMNS], train_df[LABEL_COLUMN]
    X_test, y_test = test_df[UPI_SIGNAL_COLUMNS], test_df[LABEL_COLUMN]

    base_model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        eval_metric="logloss",
        random_state=RANDOM_STATE,
    )

    # Calibrate so the score reflects a real probability, not just a rank --
    # per the pipeline spec ("calibrated PD attached to every score"). Uses
    # an inner CV split of the training data only; test_df stays untouched
    # for the final, honest AUC number.
    calibrated_model = CalibratedClassifierCV(base_model, method="isotonic", cv=5)
    calibrated_model.fit(X_train, y_train)

    test_probs = calibrated_model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, test_probs)
    brier = brier_score_loss(y_test, test_probs)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    dump(calibrated_model, ARTIFACTS_DIR / "f001_xgboost_calibrated.joblib")

    # Also fit an uncalibrated booster on the full training set for F-003's
    # native Tree SHAP contributions -- pred_contribs needs a raw Booster,
    # and contributions should explain the same feature -> outcome
    # relationship the calibrated model learned, not a second, different fit.
    raw_booster = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        eval_metric="logloss",
        random_state=RANDOM_STATE,
    )
    raw_booster.fit(X_train, y_train)
    raw_booster.save_model(str(ARTIFACTS_DIR / "f001_xgboost_raw.json"))
    raw_auc = roc_auc_score(y_test, raw_booster.predict_proba(X_test)[:, 1])

    metrics = {
        "model": "F-001 credit score (XGBoost, isotonic-calibrated)",
        "auc_target": AUC_TARGET,
        "auc_calibrated_holdout": round(float(auc), 4),
        "auc_raw_booster_holdout": round(float(raw_auc), 4),
        "brier_score_holdout": round(float(brier), 4),
        "gate_pass": bool(auc >= AUC_TARGET),
        "n_train": len(train_df),
        "n_test": len(test_df),
        "features": UPI_SIGNAL_COLUMNS,
        "caveat": (
            "Trained and evaluated entirely on synthetic data (no real Setu "
            "AA data exists yet). This AUC is a statement about the "
            "synthetic generator, not real gig-worker repayment behavior."
        ),
    }
    with open(ARTIFACTS_DIR / "f001_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics


if __name__ == "__main__":
    result = train()
    print(json.dumps(result, indent=2))
    status = "PASS" if result["gate_pass"] else "FAIL"
    print(f"\nGate A (F-001 AUC >= {AUC_TARGET}): {status} (got {result['auc_calibrated_holdout']})")
