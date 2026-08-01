"""Champion/challenger canary routing.

HONEST SCOPE: there is no live production traffic for this project yet, so
this cannot be (and does not claim to be) a live-traffic-tested canary.
What it genuinely demonstrates:
  1. Consistent-hash traffic splitting (same user always lands on the same
     arm -- a real requirement, since flip-flopping a user between models
     mid-relationship is its own kind of bug).
  2. Two ACTUALLY DIFFERENT trained models (see train_challenger.py -- not
     two copies of the same model, which would make any comparison fake).
  3. A shadow-test comparison against the held-out set (which has ground
     truth), standing in for what a real canary would compute from live
     outcomes over the following weeks.

What it does NOT do: make a real go/no-go promotion decision from live
data. Before this ever sees real traffic, `compare_arms` needs to run
against genuine post-decision outcomes (e.g. actual repayment), not the
held-out set.

Run: python -m scoring_service.api.canary
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from joblib import load
from sklearn.metrics import roc_auc_score

from scoring_service.features.feature_engineering import LABEL_COLUMN, UPI_SIGNAL_COLUMNS, split_main_dataset
from scoring_service.models.train_credit_score import prob_to_score

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "models" / "artifacts"


def assign_arm(user_id: str, challenger_traffic_pct: float) -> str:
    """Deterministic: the same user_id always maps to the same arm, so a
    user's experience doesn't flip between model versions across requests."""
    digest = hashlib.md5(user_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 10_000
    return "challenger" if bucket < challenger_traffic_pct * 10_000 else "champion"


class CanaryRouter:
    def __init__(self, challenger_traffic_pct: float = 0.10):
        self.challenger_traffic_pct = challenger_traffic_pct
        self.champion = load(ARTIFACTS_DIR / "f001_xgboost_calibrated.joblib")
        challenger_path = ARTIFACTS_DIR / "f001_challenger_calibrated.joblib"
        if not challenger_path.exists():
            raise FileNotFoundError(
                f"{challenger_path} missing -- run `python -m scoring_service.models.train_challenger` first."
            )
        self.challenger = load(challenger_path)
        self.decision_log: list[dict] = []

    def score(self, user_id: str, signals: dict) -> dict:
        arm = assign_arm(user_id, self.challenger_traffic_pct)
        model = self.champion if arm == "champion" else self.challenger

        X = pd.DataFrame([{col: signals[col] for col in UPI_SIGNAL_COLUMNS}])[UPI_SIGNAL_COLUMNS]
        prob = float(model.predict_proba(X)[0, 1])
        record = {"user_id": user_id, "arm": arm, "probability": prob, "credit_score": prob_to_score(prob)}
        self.decision_log.append(record)
        return record


def shadow_test_against_holdout(challenger_traffic_pct: float = 0.10) -> dict:
    """Runs BOTH models against the held-out test set (which has ground
    truth) and reports what each arm's AUC/approval rate would have been --
    a shadow test, not a live-traffic canary. See module docstring."""
    _, test_df = split_main_dataset()
    router = CanaryRouter(challenger_traffic_pct)

    champion_probs, challenger_probs = [], []
    champion_y, challenger_y = [], []
    arm_counts = {"champion": 0, "challenger": 0}

    for _, row in test_df.iterrows():
        user_id = row.get("user_id", "")
        arm = assign_arm(str(user_id), challenger_traffic_pct)
        arm_counts[arm] += 1
        X = pd.DataFrame([{col: row[col] for col in UPI_SIGNAL_COLUMNS}])[UPI_SIGNAL_COLUMNS]
        model = router.champion if arm == "champion" else router.challenger
        prob = float(model.predict_proba(X)[0, 1])
        if arm == "champion":
            champion_probs.append(prob)
            champion_y.append(row[LABEL_COLUMN])
        else:
            challenger_probs.append(prob)
            challenger_y.append(row[LABEL_COLUMN])

    result = {
        "challenger_traffic_pct": challenger_traffic_pct,
        "arm_counts": arm_counts,
        "champion": {
            "n": len(champion_y),
            "auc_on_its_traffic_slice": round(roc_auc_score(champion_y, champion_probs), 4) if champion_y else None,
            "mean_probability": round(sum(champion_probs) / len(champion_probs), 4) if champion_probs else None,
        },
        "challenger": {
            "n": len(challenger_y),
            "auc_on_its_traffic_slice": round(roc_auc_score(challenger_y, challenger_probs), 4) if challenger_y else None,
            "mean_probability": round(sum(challenger_probs) / len(challenger_probs), 4) if challenger_probs else None,
        },
        "caveat": (
            "This is a shadow test against the held-out synthetic set, computed by "
            "splitting that set the same way live traffic would be split -- NOT a "
            "live-traffic canary result. A real promotion decision needs actual "
            "post-decision outcomes from live traffic, observed over time."
        ),
    }
    return result


if __name__ == "__main__":
    report = shadow_test_against_holdout(challenger_traffic_pct=0.10)
    print(json.dumps(report, indent=2))
