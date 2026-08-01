"""Nightly NBFC batch scoring: re-score a portfolio of profiles in bulk.

Reuses the exact same ScoringEngine as the real-time endpoint (main.py) --
this is deliberate: a batch job that used different scoring logic than the
live API would be a classic source of silent champion/production drift.

Run: python -m scoring_service.api.batch --input scoring_service/data/synthetic_upi_dataset.csv --output /tmp/batch_scores.csv
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from scoring_service.api.scoring_engine import ScoringEngine
from scoring_service.features.feature_engineering import UPI_SIGNAL_COLUMNS


def run_batch(input_path: str, output_path: str, limit: int | None = None) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    missing = [c for c in UPI_SIGNAL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Input file missing required UPI signal columns: {missing}")
    if limit:
        df = df.head(limit)

    engine = ScoringEngine()
    start = time.perf_counter()
    results = engine.score_batch(df, geography_col="geography" if "geography" in df.columns else None)
    elapsed_s = time.perf_counter() - start

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, index=False)

    print(f"Scored {len(results)} profiles in {elapsed_s:.2f}s ({elapsed_s / max(len(results), 1) * 1000:.1f}ms/profile)")
    print(f"Approval rate: {results['approved'].mean():.3f}")
    print(f"Anomaly rate: {results['is_anomalous'].mean():.3f}")
    print(f"Wrote {output_path}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV with the 8 UPI signals (+ optional geography, user_id)")
    parser.add_argument("--output", required=True, help="Where to write scored results CSV")
    parser.add_argument("--limit", type=int, default=None, help="Score only the first N rows (for a quick test run)")
    args = parser.parse_args()
    run_batch(args.input, args.output, args.limit)


if __name__ == "__main__":
    main()
