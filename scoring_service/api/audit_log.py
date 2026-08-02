"""Real, structured audit log of every scoring decision -- append-only JSONL,
local to the running container/machine. Closes part of the "audit logs" gap
flagged in docs/PRD.md's MLOps self-assessment (section 7.1): a real, working
record of what was decided and on what basis, not a durable multi-region log
store or a queryable audit database -- that would be disproportionate infra
for this project's scale, and is documented as such rather than faked.

Each record: timestamp, endpoint, inputs, outputs, latency. Retaining the
decision basis (inputs) alongside the outcome is the actual point of an audit
log for a lending decision under RBI's Digital Lending Directions -- this is
FinBuddy's own internal record of its own decision, not data exposed
externally, so this isn't a data-minimization violation.

A write failure here must never break the actual scoring response -- it's a
side effect, not part of the request's correctness.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "scoring_audit.jsonl"

_lock = threading.Lock()


def append_record(endpoint: str, inputs: dict[str, Any], outputs: dict[str, Any], latency_ms: float) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "inputs": inputs,
        "outputs": outputs,
        "latency_ms": round(latency_ms, 2),
    }
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with _lock, LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        logger.exception("Failed to write audit log record (scoring response is unaffected)")
