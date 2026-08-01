"""End-to-end demo: pull one real profile through Setu's actual AA sandbox.

This is the "real Setu integration" story for judges -- it exercises the
genuine regulated consent-based data-sharing protocol (create consent ->
human approves via Setu's mock-FIP webview -> request data session -> fetch
decrypted FI data -> normalize into our 8 signals -> score with the trained
F-001 model). The underlying bank data is Setu's sandbox mock data, not a
real person's -- see the module docstrings in client.py/normalizer.py for
exactly what is and isn't "real" here.

THIS WILL NOT WORK until scoring_service/.env has real sandbox credentials
from https://bridge.setu.co/v2/signup. It cannot be run in this session
because those credentials don't exist yet.

Usage (run as a module so the relative imports resolve):
    python -m scoring_service.setu_integration.fetch_real_profile --vua 9999999999@setu-fip

`--vua` is the virtual user address (mobile@handle) of one of Setu's mock
FIP test accounts, given to you in the sandbox docs after signup.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .client import SetuAAClient, SetuAAConfigError
from .normalizer import normalize_session_response


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vua", required=True, help="Sandbox mock FIP test handle, e.g. 9999999999@setu-fip")
    parser.add_argument("--months", type=int, default=12, help="Consent + data range window in months")
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent.parent / "data" / "setu_real_profiles.jsonl"),
        help="Where to append normalized profiles (JSON Lines)",
    )
    args = parser.parse_args()

    try:
        client = SetuAAClient()
    except SetuAAConfigError as e:
        print(f"Cannot start: {e}", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    data_from = now - timedelta(days=30 * args.months)

    print(f"Creating consent request for {args.vua} ...")
    consent = client.create_consent(
        vua=args.vua,
        duration_months=args.months,
        data_range_from=iso(data_from),
        data_range_to=iso(now),
        fi_types=["DEPOSIT"],
    )
    print(f"Consent created: id={consent['id']}")
    print(f"Open this URL and approve via the mock FIP webview:\n  {consent['url']}")
    print("Waiting for approval (polling every 5s, 10 min timeout) ...")

    consent_status = client.wait_for_consent(consent["id"])
    if consent_status.get("status") != "ACTIVE":
        print(f"Consent did not become ACTIVE (status={consent_status.get('status')}); stopping.")
        return 1

    print("Consent ACTIVE. Requesting data session ...")
    session = client.create_data_session(
        consent_id=consent["id"], data_range_from=iso(data_from), data_range_to=iso(now)
    )
    print(f"Data session created: id={session['id']}")

    completed = client.wait_for_data_session(session["id"])
    print("Data session COMPLETED. Normalizing ...")

    profiles = normalize_session_response(completed, protected_attrs=None)
    if not profiles:
        print("No DELIVERED deposit accounts found in the session response.")
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        for profile in profiles:
            f.write(json.dumps(profile) + "\n")
            print(json.dumps(profile, indent=2))

    print(f"Appended {len(profiles)} real-sandbox profile(s) to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
