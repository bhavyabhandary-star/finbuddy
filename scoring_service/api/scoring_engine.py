"""Core scoring logic shared by the real-time FastAPI endpoint (main.py),
the nightly batch job (batch.py), and the champion/challenger router
(canary.py) -- one implementation, three callers, so a fix in one place
fixes all three instead of drifting.

Pipeline per the architecture doc: F-006 anomaly pre-check -> F-001 score +
calibration -> F-003 top-3 SHAP factors -> fairness-aware approval decision
(F-012's deployed mitigation, when geography is provided).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fairlearn.postprocessing import ThresholdOptimizer
from joblib import load

from scoring_service.features.feature_engineering import UPI_SIGNAL_COLUMNS
from scoring_service.models.explain import load_raw_booster, top3_plain_language, compute_contributions
from scoring_service.models.train_credit_score import prob_to_score

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "models" / "artifacts"

INCOME_BAND_BINS = [0, 15_000, 35_000, np.inf]
INCOME_BAND_LABELS = ["low", "medium", "high"]

Geography = Literal["urban", "semi_urban", "rural"]


def compute_income_band(avg_monthly_income: float) -> str:
    """MUST match generate_synthetic_upi_data.py's pd.cut bins exactly --
    the fairness mitigation was fit against income_band computed this way."""
    idx = np.digitize([avg_monthly_income], INCOME_BAND_BINS[1:-1])[0]
    return INCOME_BAND_LABELS[idx]


class ScoringEngine:
    """Loads every artifact once; call .score() per profile (or per row for batch)."""

    def __init__(self) -> None:
        self.calibrated_model = load(ARTIFACTS_DIR / "f001_xgboost_calibrated.joblib")
        self.raw_booster = load_raw_booster()
        self.anomaly_model = load(ARTIFACTS_DIR / "f006_isolation_forest.joblib")

        mitigator_path = ARTIFACTS_DIR / "f001_threshold_optimizer.joblib"
        self.mitigator: ThresholdOptimizer | None = load(mitigator_path) if mitigator_path.exists() else None

        audit_path = ARTIFACTS_DIR / "f012_fairness_audit.json"
        with open(audit_path) as f:
            audit = json.load(f)
        self.fallback_approval_threshold: float = audit["approval_threshold"]

    def _signals_frame(self, signals: dict) -> pd.DataFrame:
        return pd.DataFrame([{col: signals[col] for col in UPI_SIGNAL_COLUMNS}])[UPI_SIGNAL_COLUMNS]

    def score(self, signals: dict, geography: Geography | None = None) -> dict:
        """`signals` must have all 8 UPI_SIGNAL_COLUMNS keys.
        `geography` is optional -- without it, the fairness-mitigated decision
        can't be applied (it needs geography x income_band group membership),
        and the response says so explicitly rather than silently using a
        plain, un-audited threshold.
        """
        X = self._signals_frame(signals)

        # F-006 anomaly pre-check, ahead of scoring per the architecture doc.
        is_anomalous = bool(self.anomaly_model.predict(X)[0] == -1)

        # F-001 calibrated probability + score.
        prob_repay = float(self.calibrated_model.predict_proba(X)[0, 1])
        credit_score = prob_to_score(prob_repay)

        # F-003 top-3 SHAP factors (native Tree SHAP, see explain.py).
        contributions = compute_contributions(self.raw_booster, X)[0]
        top_factors = top3_plain_language(X.iloc[0], contributions)

        income_band = compute_income_band(signals["avg_monthly_income"])

        fairness_mitigation_applied = False
        if geography is not None and self.mitigator is not None:
            group_key = pd.Series([f"{geography}|{income_band}"])
            approved = bool(
                self.mitigator.predict(X, sensitive_features=group_key, random_state=42)[0]
            )
            fairness_mitigation_applied = True
        else:
            approved = bool(prob_repay >= self.fallback_approval_threshold)

        return {
            "credit_score": credit_score,
            "calibrated_probability_of_repayment": round(prob_repay, 4),
            "approved": approved,
            "fairness_mitigation_applied": fairness_mitigation_applied,
            "income_band": income_band,
            "is_anomalous": is_anomalous,
            "anomaly_note": (
                "Unusual UPI pattern detected pre-scoring -- score should be treated as "
                "lower-confidence and may warrant manual review." if is_anomalous else None
            ),
            "top_3_factors": top_factors,
        }

    def score_batch(self, df: pd.DataFrame, geography_col: str | None = "geography") -> pd.DataFrame:
        """Vectorized-ish batch path for the nightly job -- same logic as
        .score(), looped, since our models are already fast (see Phase 2/3
        latency numbers); a real high-volume nightly job would batch the
        model.predict calls themselves, but at this data scale readability
        wins."""
        results = []
        for _, row in df.iterrows():
            signals = {col: row[col] for col in UPI_SIGNAL_COLUMNS}
            geography = row[geography_col] if geography_col and geography_col in df.columns else None
            result = self.score(signals, geography=geography)
            result["user_id"] = row.get("user_id", None)
            results.append(result)
        return pd.DataFrame(results)
