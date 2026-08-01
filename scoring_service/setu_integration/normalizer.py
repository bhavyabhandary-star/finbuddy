"""Normalize a Setu AA DEPOSIT-FIType data-session payload into FinBuddy's
8 UPI signals -- the exact same schema `generate_synthetic_upi_data.py`
produces, so every downstream model (F-001/F-003/F-006) treats a real
Setu-sourced profile identically to a synthetic one.

HONEST LIMITATIONS (read before trusting these numbers):

- The AA DEPOSIT schema gives each transaction a bank-provided free-text
  `narration` field, NOT a structured merchant/category tag. There is no
  standardized "this counterparty is a UPI merchant called X" field in the
  raw FI data. So:
    * `merchant_diversity` here is an approximation: distinct normalized
      narration strings, not distinct real-world merchants. Two payments to
      the same merchant with slightly different narration text will be
      double-counted; this is a genuine limitation, not a bug to silently
      hide.
    * `b2b_ratio` here is a keyword heuristic (GST/invoice/business-sounding
      narration terms) -- it is NOT a reliable signal. Production would need
      a trained narration-classification model or a merchant-category
      lookup service; ship this heuristic labeled as such, never as ground
      truth.
- Everything else (income, regularity, tx count, balance dips, transaction
  size, tenure) is computed directly from amount/balance/timestamp fields
  that ARE part of the standardized schema, so those are on solid ground.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd

BUSINESS_KEYWORDS = re.compile(
    r"\b(?:gst|invoice|vendor|supplier|wholesale|b2b|trader|distributor|purchase\s*order)\b",
    re.IGNORECASE,
)

LOW_BALANCE_THRESHOLD_INR = 500.0


def _parse_ts(value: str) -> datetime:
    # AA timestamps are ISO8601; tolerate a trailing 'Z'.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalize_narration(narration: str) -> str:
    return re.sub(r"\s+", " ", narration or "").strip().lower()


def normalize_deposit_account(
    account_data: dict, user_id: str, protected_attrs: dict | None = None
) -> dict:
    """`account_data` is one entry of session['fips'][i]['accounts'][j]['data']['account']
    from Setu's GET /sessions/:id response, for an account of type 'deposit'.
    """
    transactions = account_data.get("transactions", {}).get("transaction", [])
    if isinstance(transactions, dict):
        transactions = [transactions]  # some AA payloads collapse a 1-item list

    if not transactions:
        raise ValueError(f"No transactions in AA payload for {user_id}; cannot normalize")

    rows = []
    for txn in transactions:
        try:
            rows.append(
                {
                    "timestamp": _parse_ts(txn["transactionTimestamp"]),
                    "amount": float(txn["amount"]),
                    "type": txn.get("type", "").upper(),  # CREDIT / DEBIT
                    "mode": txn.get("mode", "OTHER"),
                    "narration": _normalize_narration(txn.get("narration", "")),
                    "current_balance": float(txn["currentBalance"]) if txn.get("currentBalance") else None,
                }
            )
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed rows rather than fail the whole profile

    df = pd.DataFrame(rows).sort_values("timestamp")
    if df.empty:
        raise ValueError(f"All transactions malformed for {user_id}; cannot normalize")
    df["timestamp"] = df["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None)

    period_start, period_end = df["timestamp"].min(), df["timestamp"].max()
    tenure_months = max(1, round((period_end - period_start).days / 30.44))
    tenure_months = min(tenure_months, 12)  # product spec caps consent window at 12 months

    df["month"] = df["timestamp"].dt.to_period("M")
    credits = df[df["type"] == "CREDIT"]
    monthly_credit_totals = credits.groupby("month")["amount"].sum()

    avg_monthly_income = float(monthly_credit_totals.mean()) if not monthly_credit_totals.empty else 0.0
    if len(monthly_credit_totals) >= 2 and monthly_credit_totals.mean() > 0:
        cv = monthly_credit_totals.std() / monthly_credit_totals.mean()
        income_regularity_score = float(np.clip(1 - cv, 0.0, 1.0))
    else:
        income_regularity_score = 0.0

    last_30d_cutoff = period_end - pd.Timedelta(days=30)
    recent = df[df["timestamp"] >= last_30d_cutoff]
    tx_count_30d = int(len(recent))
    merchant_diversity = int(recent["narration"].nunique()) if not recent.empty else 0

    if df["current_balance"].notna().any():
        balance_dip_frequency = int((df["current_balance"] < LOW_BALANCE_THRESHOLD_INR).sum())
    else:
        balance_dip_frequency = 0

    business_like = df["narration"].str.contains(BUSINESS_KEYWORDS, na=False)
    b2b_ratio = float(business_like.mean()) if len(df) else 0.0

    avg_transaction_size = float(df["amount"].abs().mean())

    signals = {
        "user_id": user_id,
        "avg_monthly_income": round(avg_monthly_income, 2),
        "income_regularity_score": round(income_regularity_score, 4),
        "tx_count_30d": tx_count_30d,
        "merchant_diversity": merchant_diversity,
        "balance_dip_frequency": balance_dip_frequency,
        "b2b_ratio": round(b2b_ratio, 4),
        "avg_transaction_size": round(avg_transaction_size, 2),
        "tenure_months": tenure_months,
        "source": "setu_aa_sandbox",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    if protected_attrs:
        signals.update(protected_attrs)
    return signals


def normalize_session_response(session: dict, protected_attrs: dict | None = None) -> list[dict]:
    """Walk every DELIVERED deposit account in a completed data session."""
    profiles = []
    for fip in session.get("fips") or []:
        for account in fip.get("accounts", []):
            if account.get("status") != "DELIVERED":
                continue
            acc_data = account.get("data", {}).get("account", {})
            if acc_data.get("type") != "deposit":
                continue  # only DEPOSIT FIType is in scope for the 8 UPI signals
            link_ref = account.get("linkRefNumber", "unknown")
            try:
                profiles.append(
                    normalize_deposit_account(acc_data, user_id=link_ref, protected_attrs=protected_attrs)
                )
            except ValueError:
                continue
    return profiles
