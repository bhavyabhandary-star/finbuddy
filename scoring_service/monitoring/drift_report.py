"""PSI + CUSUM drift ladder per the governance spec:

  GREEN  (PSI < 0.10, no CUSUM alarm)        -> passive weekly monitoring
  AMBER  (PSI 0.10-0.20, or a CUSUM alarm)   -> shadow challenger test, no live traffic
  RED    (PSI > 0.20, or critical AUC decay) -> auto-queue retraining on fresh Setu AA data

HONEST NOTE ON WHY THIS DOESN'T USE THE `evidently` PACKAGE: evidently pulls
in pyarrow, which hit the exact same Windows Application Control block that
ruled out `shap`/numba earlier in this project -- confirmed by testing:
installing it broke `import pandas` for the ENTIRE venv, not just evidently,
since pandas unconditionally imports its pyarrow-backed extension array
module. Uninstalled immediately; it is deliberately NOT in any requirements
file used for local dev. PSI and CUSUM are standard, well-defined
statistical formulas, not something that requires the evidently package
specifically -- implemented directly here, and verified working on this
machine (see __main__ below). A thin evidently-based variant exists in
drift_report_evidently_ci.py, intended to run in GitHub Actions (Linux,
unaffected by this Windows-specific policy) for the literal branded
dashboard the spec asks for -- but that script is NOT verified from this
session, since there was no way to test it locally. Trust this file's
output over that one until it's actually been run somewhere.

HONEST NOTE ON DATA: no real production traffic exists for this project
yet. "Current" batches here are SIMULATED -- either resampled from the same
distribution as training (to verify GREEN correctly stays green) or with a
deliberate, documented shift (to verify AMBER/RED correctly fire). This is
NOT a report on real monitored drift; it demonstrates the mechanism works.

Run: python -m scoring_service.monitoring.drift_report
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scoring_service.features.feature_engineering import UPI_SIGNAL_COLUMNS, load_main_dataset

PSI_AMBER_THRESHOLD = 0.10
PSI_RED_THRESHOLD = 0.20
CUSUM_K = 0.5  # allowance (in std-devs) before CUSUM starts accumulating
CUSUM_H = 5.0  # alarm threshold (in std-devs)

REPORT_DIR = Path(__file__).resolve().parent / "reports"


def compute_psi(reference: np.ndarray, current: np.ndarray, buckets: int = 10) -> float:
    """Standard PSI: bucket edges from the REFERENCE distribution's quantiles
    (not current's), so a shift in current relative to those fixed buckets
    is exactly what gets measured."""
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, buckets + 1)))
    if len(edges) < 3:  # reference has too little spread to bucket meaningfully
        return 0.0

    ref_counts, _ = np.histogram(reference, bins=edges)
    cur_counts, _ = np.histogram(current, bins=edges)

    ref_pct = np.clip(ref_counts / max(len(reference), 1), 1e-6, None)
    cur_pct = np.clip(cur_counts / max(len(current), 1), 1e-6, None)

    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def compute_cusum_alarm(reference: np.ndarray, current_batches: list[np.ndarray]) -> dict:
    """Two-sided CUSUM over sequential batch means, standardized against the
    reference distribution's mean and STANDARD ERROR OF THE MEAN (not the
    raw population std -- a batch mean has much lower variance than an
    individual observation, so standardizing by the raw std massively
    understates how extreme a given batch-mean shift is; caught by testing:
    with the raw std, a batch mean shifted enough to put PSI deep in RED
    only produced z~-0.7, nowhere near an alarm after 5 batches). Returns
    whether an alarm fired and at which batch index."""
    ref_mean, ref_std = reference.mean(), reference.std() or 1e-9
    batch_means_z = [
        (b.mean() - ref_mean) / (ref_std / np.sqrt(max(len(b), 1))) for b in current_batches
    ]

    s_hi, s_lo = 0.0, 0.0
    alarm_at = None
    trace = []
    for i, z in enumerate(batch_means_z):
        s_hi = max(0.0, s_hi + z - CUSUM_K)
        s_lo = min(0.0, s_lo + z + CUSUM_K)
        trace.append({"batch": i, "z_mean": round(z, 4), "s_hi": round(s_hi, 4), "s_lo": round(s_lo, 4)})
        if alarm_at is None and (s_hi > CUSUM_H or s_lo < -CUSUM_H):
            alarm_at = i

    return {"alarm": alarm_at is not None, "alarm_at_batch": alarm_at, "trace": trace}


def classify(max_psi: float, cusum_alarm: bool) -> str:
    if max_psi > PSI_RED_THRESHOLD:
        return "RED"
    if max_psi >= PSI_AMBER_THRESHOLD or cusum_alarm:
        return "AMBER"
    return "GREEN"


def run_drift_report(reference_df: pd.DataFrame, current_df: pd.DataFrame, scenario_name: str) -> dict:
    per_feature_psi = {}
    for col in UPI_SIGNAL_COLUMNS:
        per_feature_psi[col] = round(compute_psi(reference_df[col].to_numpy(), current_df[col].to_numpy()), 4)

    max_psi_feature = max(per_feature_psi, key=per_feature_psi.get)
    max_psi = per_feature_psi[max_psi_feature]

    # Split current batch into 5 sequential sub-batches to give CUSUM
    # something to track over "time" -- a stand-in for weekly batches.
    sub_batches = np.array_split(current_df[max_psi_feature].to_numpy(), 5)
    cusum_result = compute_cusum_alarm(reference_df[max_psi_feature].to_numpy(), sub_batches)

    status = classify(max_psi, cusum_result["alarm"])

    return {
        "scenario": scenario_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_reference": len(reference_df),
        "n_current": len(current_df),
        "per_feature_psi": per_feature_psi,
        "max_psi_feature": max_psi_feature,
        "max_psi": max_psi,
        "cusum": {k: v for k, v in cusum_result.items() if k != "trace"},
        "cusum_trace": cusum_result["trace"],
        "status": status,
        "action": {
            "GREEN": "Passive weekly monitoring -- no action.",
            "AMBER": "Trigger a shadow challenger test. No live traffic shift.",
            "RED": "Auto-queue retraining on fresh Setu AA snapshots (real data, once available).",
        }[status],
    }


def _render_html(report: dict) -> str:
    rows = "\n".join(
        f"<tr><td>{feat}</td><td>{psi}</td>"
        f"<td>{'AMBER/RED' if psi >= PSI_AMBER_THRESHOLD else 'green'}</td></tr>"
        for feat, psi in sorted(report["per_feature_psi"].items(), key=lambda kv: -kv[1])
    )
    status_color = {"GREEN": "#1a7f37", "AMBER": "#d4a72c", "RED": "#cf222e"}[report["status"]]
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>FinBuddy Drift Report -- {report['scenario']}</title>
<style>body{{font-family:sans-serif;max-width:800px;margin:2rem auto;}}
table{{border-collapse:collapse;width:100%;}}td,th{{border:1px solid #ccc;padding:6px 10px;text-align:left;}}
.status{{font-size:1.5rem;font-weight:bold;color:{status_color};}}</style></head><body>
<h1>FinBuddy Drift Report</h1>
<p><b>Scenario:</b> {report['scenario']} &nbsp; <b>Generated:</b> {report['generated_at']}</p>
<p class="status">Status: {report['status']}</p>
<p><b>Action:</b> {report['action']}</p>
<p><b>Reference rows:</b> {report['n_reference']} &nbsp; <b>Current rows:</b> {report['n_current']}</p>
<h2>Per-feature PSI</h2>
<table><tr><th>Feature</th><th>PSI</th><th>Flag</th></tr>{rows}</table>
<h2>CUSUM (on {report['max_psi_feature']}, highest-PSI feature)</h2>
<p>Alarm fired: {report['cusum']['alarm']} (at batch {report['cusum']['alarm_at_batch']})</p>
<p style="color:#666;font-size:0.9em">PSI thresholds: GREEN &lt; {PSI_AMBER_THRESHOLD}, AMBER {PSI_AMBER_THRESHOLD}-{PSI_RED_THRESHOLD}, RED &gt; {PSI_RED_THRESHOLD}.
Simulated data -- see module docstring for why (no real production traffic exists yet).</p>
</body></html>"""


def _simulate_shifted_batch(reference_df: pd.DataFrame, n: int, income_shift: float) -> pd.DataFrame:
    """Deliberately shifted synthetic 'current' batch -- simulates an
    economic-downturn-style drift (lower income) to verify AMBER/RED fire
    correctly. income_shift is a multiplier, calibrated empirically against
    this exact dataset (see scratch calibration, not guessed): 0.85 lands
    in AMBER (PSI ~0.116), 0.65 lands in RED (PSI ~0.736).

    balance_dip_frequency deliberately NOT shifted here -- it's a
    low-cardinality integer feature where quantile-based PSI bucketing is
    numerically unstable (verified: a small shift caused PSI to jump
    discontinuously from 0.001 to 1.6, an artifact of bucket-edge
    collapsing on discrete data, not a real 160x drift). Real deployment
    monitoring PSI on discrete features would need count-based (not
    quantile-based) bucketing -- flagged here, not silently worked around."""
    sample = reference_df.sample(n=n, replace=True, random_state=123).copy()
    sample["avg_monthly_income"] = sample["avg_monthly_income"] * income_shift
    return sample


if __name__ == "__main__":
    import sys

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    reference_df = load_main_dataset()

    scenarios = {
        "no_drift_control": reference_df.sample(n=1500, replace=True, random_state=7),
        "moderate_drift_amber": _simulate_shifted_batch(reference_df, 1500, income_shift=0.85),
        "severe_drift_red": _simulate_shifted_batch(reference_df, 1500, income_shift=0.65),
    }

    for name, current_df in scenarios.items():
        report = run_drift_report(reference_df, current_df, scenario_name=name)
        with open(REPORT_DIR / f"{name}.json", "w") as f:
            json.dump(report, f, indent=2)
        with open(REPORT_DIR / f"{name}.html", "w", encoding="utf-8") as f:
            f.write(_render_html(report))
        print(f"{name}: status={report['status']} max_psi={report['max_psi']} ({report['max_psi_feature']}) "
              f"cusum_alarm={report['cusum']['alarm']}")

    print(f"\nReports written to {REPORT_DIR}")
