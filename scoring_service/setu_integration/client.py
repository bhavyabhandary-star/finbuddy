"""Thin client for Setu's Account Aggregator (AA) Gateway API.

WHAT THIS IS AND ISN'T, HONESTLY:

- The endpoint paths and request/response field names below (POST /consents,
  GET /consents/:id, POST /sessions, GET /sessions/:id) are taken directly
  from Setu's public docs (docs.setu.co/data/account-aggregator/...), not
  guessed.
- The exact base URL and the exact auth header names are NOT publicly
  documented -- Setu gates them behind a free developer signup at
  https://bridge.setu.co/v2/signup, where you register an FIU, create an
  "Account Aggregator" product, and get a per-product Postman collection plus
  x-client-id / x-client-secret / x-product-instance-id credentials. This
  client reads those from environment variables and is built to match the
  header names Setu's onboarding docs name explicitly, but you MUST diff
  this against the Postman collection your product page gives you the first
  time you run it against the sandbox -- do not assume it's correct
  untested.
- Setu's data-session API returns already-DECRYPTED FI data (Setu handles
  the AA ecosystem's ECDH key-exchange/decryption on your behalf). That's
  why this client has no crypto in it -- there genuinely isn't any needed on
  our side for the sandbox flow.
- Sandbox consent approval still requires a human to open `consent.url` and
  click through Setu's mock-FIP webview (there is no headless/API way to
  auto-approve a sandbox consent) -- this is a live protocol interaction,
  not a mock.

Env vars required (see ../.env.example):
  SETU_BASE_URL              e.g. https://fiu-uat.setu.co  (confirm with Setu)
  SETU_CLIENT_ID
  SETU_CLIENT_SECRET
  SETU_PRODUCT_INSTANCE_ID
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


class SetuAAConfigError(RuntimeError):
    pass


class SetuAAError(RuntimeError):
    def __init__(self, message: str, response: requests.Response | None = None):
        super().__init__(message)
        self.response = response


@dataclass
class SetuAAConfig:
    base_url: str
    client_id: str
    client_secret: str
    product_instance_id: str

    @classmethod
    def from_env(cls) -> "SetuAAConfig":
        base_url = os.environ.get("SETU_BASE_URL", "").rstrip("/")
        client_id = os.environ.get("SETU_CLIENT_ID", "")
        client_secret = os.environ.get("SETU_CLIENT_SECRET", "")
        product_instance_id = os.environ.get("SETU_PRODUCT_INSTANCE_ID", "")
        missing = [
            name
            for name, val in [
                ("SETU_BASE_URL", base_url),
                ("SETU_CLIENT_ID", client_id),
                ("SETU_CLIENT_SECRET", client_secret),
                ("SETU_PRODUCT_INSTANCE_ID", product_instance_id),
            ]
            if not val
        ]
        if missing:
            raise SetuAAConfigError(
                "Missing Setu AA sandbox credentials in environment: "
                + ", ".join(missing)
                + ". Sign up at https://bridge.setu.co/v2/signup, create an "
                "Account Aggregator product, and put the credentials in "
                "scoring_service/.env (see .env.example)."
            )
        return cls(base_url, client_id, client_secret, product_instance_id)


class SetuAAClient:
    """Consent + FI-data-session flow against Setu's AA Gateway."""

    def __init__(self, config: SetuAAConfig | None = None):
        self.config = config or SetuAAConfig.from_env()

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-client-id": self.config.client_id,
            "x-client-secret": self.config.client_secret,
            "x-product-instance-id": self.config.product_instance_id,
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        resp = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        if not resp.ok:
            raise SetuAAError(
                f"Setu AA API {method} {path} failed: {resp.status_code} {resp.text}", resp
            )
        return resp.json()

    # -- Consent flow ------------------------------------------------------

    def create_consent(
        self,
        vua: str,
        duration_months: int = 12,
        data_range_from: str | None = None,
        data_range_to: str | None = None,
        fi_types: list[str] | None = None,
        purpose_text: str = "Credit scoring for gig-economy lending (FinBuddy)",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """POST /consents -- returns {id, url, status, detail...}.

        `url` is the consent webview link a human must open to approve/reject
        in the sandbox (using a Setu mock FIP test account).
        """
        body: dict[str, Any] = {
            "consentDuration": {"unit": "MONTH", "value": str(duration_months)},
            "vua": vua,
            "context": [],
            "additionalParams": {"tags": tags or ["FinBuddy_Credit_Scoring"]},
        }
        if data_range_from and data_range_to:
            body["dataRange"] = {"from": data_range_from, "to": data_range_to}
        return self._request("POST", "/consents", json=body)

    def get_consent_status(self, consent_id: str, expanded: bool = True) -> dict[str, Any]:
        """GET /consents/:id -- status in {PENDING, ACTIVE, REJECTED, REVOKED, EXPIRED}."""
        params = {"expanded": "true"} if expanded else {}
        return self._request("GET", f"/consents/{consent_id}", params=params)

    def wait_for_consent(
        self, consent_id: str, poll_seconds: int = 5, timeout_seconds: int = 600
    ) -> dict[str, Any]:
        """Poll until the human has approved/rejected the consent in the webview."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            status = self.get_consent_status(consent_id)
            if status.get("status") in ("ACTIVE", "REJECTED", "REVOKED", "EXPIRED"):
                return status
            time.sleep(poll_seconds)
        raise TimeoutError(f"Consent {consent_id} did not resolve within {timeout_seconds}s")

    def revoke_consent(self, consent_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v2/consents/{consent_id}/revoke")

    # -- Data fetch flow -----------------------------------------------------

    def create_data_session(
        self,
        consent_id: str,
        data_range_from: str,
        data_range_to: str,
        response_format: str = "json",
    ) -> dict[str, Any]:
        """POST /sessions -- kicks off data prep at the linked FIP(s)."""
        body = {
            "consentId": consent_id,
            "dataRange": {"from": data_range_from, "to": data_range_to},
            "format": response_format,
        }
        return self._request("POST", "/sessions", json=body)

    def get_data_session(self, session_id: str) -> dict[str, Any]:
        """GET /sessions/:id -- decrypted FI data once ready.

        status: PENDING (not ready) / PARTIAL (some FIPs delivered) /
        COMPLETED (all delivered).
        """
        return self._request("GET", f"/sessions/{session_id}")

    def wait_for_data_session(
        self, session_id: str, poll_seconds: int = 5, timeout_seconds: int = 300
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            session = self.get_data_session(session_id)
            if session.get("status") == "COMPLETED":
                return session
            time.sleep(poll_seconds)
        raise TimeoutError(f"Data session {session_id} did not complete within {timeout_seconds}s")
