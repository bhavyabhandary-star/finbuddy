"""Real, structured audit log of every coach interaction (HTTP API and
WhatsApp webhook both use this) -- append-only JSONL, local to the running
container. Same rationale as scoring_service/api/audit_log.py: closes part
of the "audit logs" gap in docs/PRD.md section 7.1 honestly, without
pretending this is a durable multi-region log store.

Logs the query, the retrieved sources (not the full corpus chunks -- just
metadata, to keep records small), the answer, and whether it escalated --
the actual basis for compliance review of what the coach told a borrower
and why.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "coach_audit.jsonl"

_lock = threading.Lock()


def append_record(
    channel: str,
    query: str,
    answer: str,
    escalate_to_human: bool,
    low_confidence: bool,
    sources: list[dict[str, Any]],
    latency_ms: float,
) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel": channel,  # "http_api" or "whatsapp"
        "query": query,
        "answer": answer,
        "escalate_to_human": escalate_to_human,
        "low_confidence": low_confidence,
        "sources": sources,
        "latency_ms": round(latency_ms, 2),
    }
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with _lock, LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        logger.exception("Failed to write coach audit log record (response is unaffected)")
