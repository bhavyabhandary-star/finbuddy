"""Two things this project didn't have a single command for yet:

1. Champion-vs-challenger PREDICTION drift -- how differently do the two
   F-001 models score the SAME held-out borrowers? (Different from
   monitoring/drift_report.py, which measures FEATURE drift for one model
   over time -- this measures OUTPUT divergence between two model versions
   on identical inputs, right now.) Reuses drift_report.py's real, tested
   PSI implementation rather than duplicating it.
2. Accuracy / precision / recall / F1 / confusion matrix for F-001
   (champion + challenger) and the Risk-Trend classifier -- none of the
   existing metrics.json files have these (they report AUC/ROC-AUC and
   Brier score, since F-001 is fundamentally a probability/PD model, not a
   hard classifier). Computed here at real, already-established decision
   thresholds:
     - F-001: the actual deployed approval_threshold (0.3288) from
       f012_fairness_audit.json -- NOT an arbitrary 0.5, since that's not
       the threshold this system actually uses to approve/deny.
     - Risk-Trend: 0.5, since it has no separately-audited approval
       threshold of its own (it's a portfolio-monitoring signal, not a
       lending decision).

All numbers are on the same synthetic held-out test set as every other
metric in this project -- see README's "what's real vs demo-grade" table
for what that does and doesn't mean.

Run: python -m scoring_service.models.evaluate_classification
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import load
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

from scoring_service.features.feature_engineering import (
    LABEL_COLUMN,
    UPI_SIGNAL_COLUMNS,
    split_main_dataset,
    split_risk_trend_dataset,
)
from scoring_service.monitoring.drift_report import compute_psi

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "monitoring" / "reports"

RISK_TREND_FEATURES = [f"delta_{col}" for col in UPI_SIGNAL_COLUMNS]


def _classification_metrics(y_true, y_prob, threshold: float) -> dict:
    y_pred = (np.asarray(y_prob) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "threshold": threshold,
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
        "confusion_matrix": {
            "true_negative": int(tn), "false_positive": int(fp),
            "false_negative": int(fn), "true_positive": int(tp),
        },
    }


def evaluate_f001_champion_vs_challenger() -> dict:
    _, test_df = split_main_dataset()
    X_test = test_df[UPI_SIGNAL_COLUMNS]
    y_test = test_df[LABEL_COLUMN].to_numpy()

    champion = load(ARTIFACTS_DIR / "f001_xgboost_calibrated.joblib")
    challenger = load(ARTIFACTS_DIR / "f001_challenger_calibrated.joblib")

    champion_prob = champion.predict_proba(X_test)[:, 1]
    challenger_prob = challenger.predict_proba(X_test)[:, 1]

    with open(ARTIFACTS_DIR / "f012_fairness_audit.json") as f:
        approval_threshold = json.load(f)["approval_threshold"]

    champion_metrics = _classification_metrics(y_test, champion_prob, approval_threshold)
    challenger_metrics = _classification_metrics(y_test, challenger_prob, approval_threshold)

    champion_decision = (champion_prob >= approval_threshold).astype(int)
    challenger_decision = (challenger_prob >= approval_threshold).astype(int)
    decision_flip_rate = float((champion_decision != challenger_decision).mean())

    return {
        "n_test": len(y_test),
        "champion": champion_metrics,
        "challenger": challenger_metrics,
        "prediction_drift_champion_vs_challenger": {
            "psi_on_probability_output": round(compute_psi(champion_prob, challenger_prob), 4),
            "mean_absolute_probability_difference": round(float(np.mean(np.abs(champion_prob - challenger_prob))), 4),
            "approve_deny_decision_flip_rate": round(decision_flip_rate, 4),
            "interpretation": (
                "PSI here compares the TWO MODELS' output distributions on the same "
                "borrowers, not one model's drift over time (that's monitoring/"
                "drift_report.py's job). Same PSI bands apply loosely: <0.1 near-"
                "identical behavior, 0.1-0.25 some divergence, >0.25 the challenger "
                "would meaningfully change who gets approved -- worth human review "
                "before promotion, not an automated go/no-go."
            ),
        },
    }


def evaluate_risk_trend() -> dict:
    _, test_df = split_risk_trend_dataset()
    X_test = test_df[RISK_TREND_FEATURES]
    y_test = test_df["trend_label"].to_numpy()

    model = load(ARTIFACTS_DIR / "risk_trend_logreg.joblib")
    prob = model.predict_proba(X_test)[:, 1]

    return {"n_test": len(y_test), **_classification_metrics(y_test, prob, threshold=0.5)}


def main() -> None:
    report = {
        "f001_champion_vs_challenger": evaluate_f001_champion_vs_challenger(),
        "risk_trend": evaluate_risk_trend(),
        "caveat": (
            "All figures on synthetic held-out data -- see README's 'what's real "
            "vs demo-grade' table. Champion/challenger prediction-drift PSI is a "
            "shadow-test proxy (see canary.py), not a live-traffic result."
        ),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "classification_metrics.json"
    out_path.write_text(json.dumps(report, indent=2))

    print(f"Wrote {out_path}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
