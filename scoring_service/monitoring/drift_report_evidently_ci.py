"""Literal Evidently AI dashboard, for the exact deliverable the spec asks
for ("point Evidently AI at the deployed endpoint; capture a real
dashboard view"). Intended to run in GitHub Actions (Linux) or any machine
without this project's Windows-specific Application Control restriction.

NOT VERIFIED FROM THIS SESSION -- there was no way to run this locally
(installing `evidently` pulls in pyarrow, which hit the same blocked-DLL
issue that ruled out `shap`; confirmed it broke `import pandas` for the
whole venv, uninstalled immediately). Written against evidently's current
documented API (Report + DataDriftPreset + .save_html()) as of the
research done for this file, but has not actually been executed. Trust
drift_report.py's output (pure-numpy PSI + CUSUM, tested and verified on
this machine) over this file's until this has actually been run somewhere
and confirmed working -- treat this as a follow-up task, not a finished
deliverable.

Requires: pip install -r scoring_service/monitoring/requirements-evidently-ci.txt
(deliberately NOT in the main requirements.txt -- see drift_report.py's
docstring for why).

Run (on a machine/CI runner without the Windows DLL restriction):
    python -m scoring_service.monitoring.drift_report_evidently_ci
"""

from __future__ import annotations

from pathlib import Path

from scoring_service.features.feature_engineering import UPI_SIGNAL_COLUMNS, load_main_dataset
from scoring_service.monitoring.drift_report import _simulate_shifted_batch

REPORT_DIR = Path(__file__).resolve().parent / "reports"


def main() -> None:
    from evidently import Report
    from evidently.presets import DataDriftPreset

    reference_df = load_main_dataset()[UPI_SIGNAL_COLUMNS]

    scenarios = {
        "evidently_no_drift_control": reference_df.sample(n=1500, replace=True, random_state=7),
        "evidently_moderate_drift_amber": _simulate_shifted_batch(load_main_dataset(), 1500, income_shift=0.85)[UPI_SIGNAL_COLUMNS],
        "evidently_severe_drift_red": _simulate_shifted_batch(load_main_dataset(), 1500, income_shift=0.65)[UPI_SIGNAL_COLUMNS],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    for name, current_df in scenarios.items():
        report = Report([DataDriftPreset(method="psi")])
        result = report.run(reference_data=reference_df, current_data=current_df)
        out_path = REPORT_DIR / f"{name}.html"
        result.save_html(str(out_path))
        print(f"{name}: wrote {out_path}")


if __name__ == "__main__":
    main()
