"""Shared train/test split for every scoring_service model.

Every training script (F-001, F-006, F-012's audit, Risk-Trend) must
evaluate on the SAME held-out test set, or metrics/fairness numbers from
different scripts aren't comparable. This is the single source of truth
for that split.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

UPI_SIGNAL_COLUMNS = [
    "avg_monthly_income",
    "income_regularity_score",
    "tx_count_30d",
    "merchant_diversity",
    "balance_dip_frequency",
    "b2b_ratio",
    "avg_transaction_size",
    "tenure_months",
]

PROTECTED_ATTR_COLUMNS = ["gender", "geography", "income_band"]

LABEL_COLUMN = "repaid_on_time"
ANOMALY_COLUMN = "is_anomalous"

RANDOM_STATE = 42
TEST_SIZE = 0.2


def load_main_dataset() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "synthetic_upi_dataset.csv")


def load_risk_trend_dataset() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "synthetic_risk_trend_dataset.csv")


def split_main_dataset(
    df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stratified on the repayment label so both splits keep the same base rate."""
    if df is None:
        df = load_main_dataset()
    train_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=df[LABEL_COLUMN],
    )
    return train_df.reset_index(drop=True), test_df.reset_index(drop=True)


def split_risk_trend_dataset(
    df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df is None:
        df = load_risk_trend_dataset()
    train_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=df["trend_label"],
    )
    return train_df.reset_index(drop=True), test_df.reset_index(drop=True)
