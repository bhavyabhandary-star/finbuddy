"""Lightweight model registry -- NOT MLflow/SageMaker-style (no staging/
promotion API, no server), but every field in it is real: each artifact's
git commit hash and commit date come from `git log` against the actual
tracked file, and every metric comes from that model's own real
`*_metrics.json` (or `f012_fairness_audit.json`), not invented.

This closes the "model registry" gap flagged in docs/PRD.md's MLOps
self-assessment as honestly as the project's scale supports: a real,
regeneratable inventory of what's deployed, its lineage, and its metrics --
without pretending this is a full registry service with promotion
workflows, which would be disproportionate infrastructure for one
developer's models.

Run: python -m scoring_service.models.registry
Regenerates scoring_service/models/artifacts/registry.json.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
REPO_ROOT = Path(__file__).resolve().parent  # any dir inside the repo works for `git log`

# (artifact_file, metrics_file, status, role) -- status/role are the only
# hand-classified fields here; everything else is read from real files.
MODELS: list[tuple[str, str | None, str, str]] = [
    ("f001_xgboost_calibrated.joblib", "f001_metrics.json", "production", "F-001 credit score (champion)"),
    ("f001_challenger_calibrated.joblib", "f001_challenger_metrics.json", "challenger", "F-001 credit score (challenger, see canary.py)"),
    ("f001_threshold_optimizer.joblib", None, "production", "F-012 fairness mitigator (ThresholdOptimizer), wraps F-001 champion"),
    ("risk_trend_logreg.joblib", "risk_trend_metrics.json", "production", "Risk-Trend classifier"),
    ("f006_isolation_forest.joblib", "f006_metrics.json", "production", "F-006 anomaly detector"),
]

FAIRNESS_AUDIT_FILE = "f012_fairness_audit.json"


def _git_info(path: Path) -> dict[str, str | None]:
    """Real last-commit hash/date for this exact file, from git history --
    not a fabricated version number."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%H|%aI", "--", str(path)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        line = out.stdout.strip()
        if not line:
            return {"commit": None, "committed_at": None}
        commit, committed_at = line.split("|", 1)
        return {"commit": commit, "committed_at": committed_at}
    except Exception:
        return {"commit": None, "committed_at": None}


def build_registry() -> dict[str, Any]:
    entries = []
    for artifact_file, metrics_file, status, role in MODELS:
        artifact_path = ARTIFACTS_DIR / artifact_file
        if not artifact_path.exists():
            continue

        metrics: dict[str, Any] = {}
        if metrics_file:
            metrics_path = ARTIFACTS_DIR / metrics_file
            if metrics_path.exists():
                metrics = json.loads(metrics_path.read_text())

        entries.append(
            {
                "artifact": artifact_file,
                "role": role,
                "status": status,
                "size_bytes": artifact_path.stat().st_size,
                **_git_info(artifact_path),
                "metrics": metrics,
            }
        )

    fairness_path = ARTIFACTS_DIR / FAIRNESS_AUDIT_FILE
    fairness_summary = None
    if fairness_path.exists():
        audit = json.loads(fairness_path.read_text())
        fairness_summary = {
            "artifact": FAIRNESS_AUDIT_FILE,
            **_git_info(fairness_path),
            "approval_threshold": audit.get("approval_threshold"),
        }

    return {
        "generated_by": "scoring_service/models/registry.py",
        "note": "Not a full model-registry service (no staging/promotion API) -- a real, regeneratable inventory. See docs/PRD.md section 7.1.",
        "models": entries,
        "fairness_audit": fairness_summary,
    }


def main() -> None:
    registry = build_registry()
    out_path = ARTIFACTS_DIR / "registry.json"
    out_path.write_text(json.dumps(registry, indent=2))

    print(f"Wrote {out_path}\n")
    for entry in registry["models"]:
        print(f"[{entry['status']:^11}] {entry['role']}")
        print(f"    artifact: {entry['artifact']} ({entry['size_bytes']:,} bytes)")
        print(f"    commit:   {entry['commit']} ({entry['committed_at']})")
        if entry["metrics"]:
            key_metric = {k: v for k, v in entry["metrics"].items() if "auc" in k.lower() or "precision" in k.lower()}
            print(f"    metrics:  {key_metric}")
        print()


if __name__ == "__main__":
    main()
