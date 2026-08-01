"""Synthetic UPI transaction-signal generator for FinBuddy's scoring pipeline.

NO REAL SETU AA DATA EXISTS FOR THIS PROJECT. Every dataset produced here is
synthetic. Every AUC/SPD/DIR number computed downstream from this data is a
statement about this generator, not about real gig-worker repayment
behavior. Before any lending decision relies on F-001/F-006/F-012, the
models must be retrained on real, consented Setu Account Aggregator data.

Produces two files:

1. synthetic_upi_dataset.csv — one row per synthetic gig worker, the 8 UPI
   signals feeding F-001 (credit score) and F-006 (anomaly detection), plus
   three protected attributes (gender, geography, income_band) used only for
   the F-012 fairness audit (never as model features), plus the repayment
   outcome label used to train/validate F-001.

2. synthetic_risk_trend_dataset.csv — two 6-month windows (early/late) per
   worker with a controlled improving/decaying trend label, for the
   Risk-Trend logistic regression.

The 8 UPI signals (documented here because every downstream script assumes
this exact schema):

  1. avg_monthly_income       -- mean monthly UPI credit volume (INR)
  2. income_regularity_score  -- 0-1, higher = more regular month-to-month
                                  income (inverse coefficient of variation)
  3. tx_count_30d             -- UPI transaction count in a trailing 30 days
  4. merchant_diversity       -- distinct merchants/counterparties in 30 days
  5. balance_dip_frequency    -- times/month balance fell below a low-buffer
                                  threshold
  6. b2b_ratio                -- 0-1, share of inflow that is B2B/business
                                  receipts vs. consumer/gig-platform payouts
  7. avg_transaction_size     -- mean UPI transaction amount (INR)
  8. tenure_months            -- months of UPI history available (AA consent
                                  window, up to 12 per the product spec)

Indirect bias is baked in deliberately (geography and, more mildly, gender
shift the *feature* distributions, not the label directly) so the F-012
fairness audit in Phase 3 has a genuine proxy-bias problem to detect and
mitigate rather than a synthetic strawman that trivially passes.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RNG_SEED = 42
N_USERS = 10_000
ANOMALY_FRACTION = 0.03

GENDERS = ["male", "female", "other"]
GENDER_PROBS = [0.62, 0.36, 0.02]  # reflects skew in gig-platform driver/delivery rosters

GEOGRAPHIES = ["urban", "semi_urban", "rural"]
GEOGRAPHY_PROBS = [0.45, 0.35, 0.20]


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _zscore(x: np.ndarray) -> np.ndarray:
    return (x - x.mean()) / (x.std() + 1e-9)


def generate_base_cohort(rng: np.random.Generator, n: int) -> pd.DataFrame:
    gender = rng.choice(GENDERS, size=n, p=GENDER_PROBS)
    geography = rng.choice(GEOGRAPHIES, size=n, p=GEOGRAPHY_PROBS)

    # Geography shifts the *feature-generating process*, not the label
    # directly -- this is what makes it a proxy-bias problem rather than a
    # direct-discrimination one.
    geo_income_shift = np.select(
        [geography == "urban", geography == "semi_urban", geography == "rural"],
        [1.15, 1.0, 0.80],
    )
    geo_merchant_shift = np.select(
        [geography == "urban", geography == "semi_urban", geography == "rural"],
        [1.20, 1.0, 0.75],
    )
    # Small, real-world-plausible gap; deliberately mild vs. the geography effect.
    gender_income_shift = np.where(gender == "female", 0.93, 1.0)

    base_income = rng.lognormal(mean=9.6, sigma=0.45, size=n)  # ~INR 15k median
    avg_monthly_income = base_income * geo_income_shift * gender_income_shift
    avg_monthly_income = np.clip(avg_monthly_income, 4_000, 150_000)

    income_regularity_score = np.clip(
        rng.beta(a=5, b=2.2, size=n) * (0.85 + 0.15 * (geography == "urban")), 0.05, 0.99
    )

    tx_count_30d = np.clip(
        rng.negative_binomial(n=8, p=0.05, size=n).astype(float) * geo_merchant_shift * 0.15
        + 20,
        5,
        3000,
    )

    merchant_diversity = np.clip(
        (rng.poisson(lam=10, size=n) * geo_merchant_shift).astype(float) + 1, 1, 400
    )

    balance_dip_frequency = np.clip(
        rng.poisson(lam=np.where(geography == "rural", 3.2, 1.4), size=n).astype(float), 0, 20
    )

    b2b_ratio = np.clip(rng.beta(a=1.5, b=4.0, size=n), 0.0, 1.0)

    avg_transaction_size = np.clip(
        avg_monthly_income / np.clip(tx_count_30d, 5, None) * rng.uniform(0.7, 1.3, size=n),
        20,
        50_000,
    )

    tenure_months = rng.integers(low=1, high=13, size=n)

    df = pd.DataFrame(
        {
            "user_id": [f"synthetic_user_{i:06d}" for i in range(n)],
            "gender": gender,
            "geography": geography,
            "avg_monthly_income": avg_monthly_income.round(2),
            "income_regularity_score": income_regularity_score.round(4),
            "tx_count_30d": tx_count_30d.round(0).astype(int),
            "merchant_diversity": merchant_diversity.round(0).astype(int),
            "balance_dip_frequency": balance_dip_frequency.round(0).astype(int),
            "b2b_ratio": b2b_ratio.round(4),
            "avg_transaction_size": avg_transaction_size.round(2),
            "tenure_months": tenure_months,
        }
    )

    income_band = pd.cut(
        df["avg_monthly_income"],
        bins=[0, 15_000, 35_000, np.inf],
        labels=["low", "medium", "high"],
    )
    df["income_band"] = income_band.astype(str)

    return df


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


def assign_repayment_label(rng: np.random.Generator, df: pd.DataFrame) -> pd.DataFrame:
    """Latent creditworthiness -> Bernoulli repayment outcome.

    Protected attributes are NOT inputs to this function -- only the 8 UPI
    signals drive the label, exactly as F-001 will only ever see the 8
    signals at inference time. Any disparity the fairness audit finds later
    is therefore a genuine proxy effect flowing through the feature
    distributions above, not a label leak.
    """
    latent = (
        0.90 * _zscore(df["income_regularity_score"].to_numpy())
        + 0.55 * _zscore(np.log1p(df["avg_monthly_income"].to_numpy()))
        + 0.40 * _zscore(df["merchant_diversity"].to_numpy())
        - 0.60 * _zscore(df["balance_dip_frequency"].to_numpy())
        + 0.30 * _zscore(df["b2b_ratio"].to_numpy())
        + 0.35 * _zscore(df["tenure_months"].to_numpy())
        + 0.20 * _zscore(df["tx_count_30d"].to_numpy())
        + rng.normal(scale=0.55, size=len(df))  # irreducible noise
    )
    prob_good = _sigmoid(latent)
    label = rng.binomial(1, prob_good)

    # Map probability to the 300-850 product range for reference/UX use
    # (this is NOT the model's calibrated output -- that comes from F-001's
    # own calibration in Phase 2 -- it's just a sanity-check column here).
    credit_score_reference = (300 + prob_good * 550).round(0).astype(int)

    df = df.copy()
    df["repaid_on_time"] = label
    df["_prob_good_reference"] = prob_good.round(4)
    df["credit_score_reference"] = credit_score_reference
    return df


def inject_anomalies(rng: np.random.Generator, df: pd.DataFrame, fraction: float) -> pd.DataFrame:
    """Flip a small fraction of rows into out-of-distribution UPI patterns.

    Ground-truth anomaly flags exist ONLY so Phase 2 can report honest
    precision/recall for the unsupervised Isolation Forest -- F-006 itself
    never sees this column.
    """
    df = df.copy()
    n = len(df)
    n_anom = int(n * fraction)
    anom_idx = rng.choice(n, size=n_anom, replace=False)

    df["is_anomalous"] = False
    df.loc[anom_idx, "is_anomalous"] = True

    kind = rng.choice(["balance_shock", "volume_spike", "merchant_collapse"], size=n_anom)

    balance_shock_idx = anom_idx[kind == "balance_shock"]
    df.loc[balance_shock_idx, "balance_dip_frequency"] = rng.integers(15, 40, size=len(balance_shock_idx))

    volume_spike_idx = anom_idx[kind == "volume_spike"]
    df.loc[volume_spike_idx, "tx_count_30d"] = rng.integers(2000, 6000, size=len(volume_spike_idx))

    merchant_collapse_idx = anom_idx[kind == "merchant_collapse"]
    df.loc[merchant_collapse_idx, "merchant_diversity"] = 1
    df.loc[merchant_collapse_idx, "avg_transaction_size"] = rng.uniform(15_000, 50_000, size=len(merchant_collapse_idx))

    return df


def generate_risk_trend_dataset(rng: np.random.Generator, base_df: pd.DataFrame) -> pd.DataFrame:
    """Two 6-month windows per user with a controlled improving/decaying trend.

    trend_label = 1 (improving) or 0 (decaying). Feature set is the delta
    (late - early) of each of the 8 signals, normalized, which is what the
    Featured Risk-Trend logistic regression trains on.
    """
    n = len(base_df)
    direction = rng.choice([1, -1], size=n)  # +1 improving, -1 decaying
    magnitude = rng.uniform(0.15, 0.55, size=n)  # how much the window shifts

    early = base_df[UPI_SIGNAL_COLUMNS].copy()
    late = base_df[UPI_SIGNAL_COLUMNS].copy()

    # Signals that should rise when things improve; dip frequency is inverse.
    improving_cols = [
        "avg_monthly_income",
        "income_regularity_score",
        "tx_count_30d",
        "merchant_diversity",
        "b2b_ratio",
    ]
    for col in improving_cols:
        shift = 1 + direction * magnitude * rng.uniform(0.6, 1.0, size=n)
        late[col] = early[col] * shift

    late["balance_dip_frequency"] = np.clip(
        early["balance_dip_frequency"] * (1 - direction * magnitude), 0, None
    )
    late["tenure_months"] = early["tenure_months"] + 6

    delta = pd.DataFrame(
        {f"delta_{c}": _zscore((late[c] - early[c]).to_numpy()) for c in UPI_SIGNAL_COLUMNS}
    )
    delta["user_id"] = base_df["user_id"].to_numpy()
    delta["trend_label"] = (direction > 0).astype(int)  # 1 = improving
    # a touch of label noise so ROC-AUC lands near-but-not-implausibly-above target
    flip = rng.random(n) < 0.02
    delta.loc[flip, "trend_label"] = 1 - delta.loc[flip, "trend_label"]

    return delta


def main() -> None:
    rng = np.random.default_rng(RNG_SEED)

    base = generate_base_cohort(rng, N_USERS)
    labeled = assign_repayment_label(rng, base)
    with_anomalies = inject_anomalies(rng, labeled, ANOMALY_FRACTION)

    trend = generate_risk_trend_dataset(rng, base)

    out_dir = Path(__file__).resolve().parent
    main_path = out_dir / "synthetic_upi_dataset.csv"
    trend_path = out_dir / "synthetic_risk_trend_dataset.csv"

    with_anomalies.to_csv(main_path, index=False)
    trend.to_csv(trend_path, index=False)

    print(f"Wrote {len(with_anomalies)} rows -> {main_path}")
    print(f"  repaid_on_time positive rate: {with_anomalies['repaid_on_time'].mean():.3f}")
    print(f"  anomalous rows: {int(with_anomalies['is_anomalous'].sum())}")
    print(f"Wrote {len(trend)} rows -> {trend_path}")
    print(f"  trend_label (improving) positive rate: {trend['trend_label'].mean():.3f}")


if __name__ == "__main__":
    main()
