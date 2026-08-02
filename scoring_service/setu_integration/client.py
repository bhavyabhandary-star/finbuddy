"""Thin client for Setu's Account Aggregator (AA) Gateway V2 API.

WHAT THIS IS AND ISN'T, HONESTLY:

- CONFIRMED WORKING END-TO-END on 2026-08-02: POST /v2/consents against the
  live sandbox, with this project's real Bridge credentials, returned a real
  HTTP 201 with a real consent id and human-approval URL. Every endpoint,
  header, and body field below is what that verified call actually used --
  not copied from prose docs.
- The real API is VERSIONED (/v2/consents, /v2/sessions, ...). Setu's public
  prose docs (docs.setu.co/data/account-aggregator/...) never mention the
  version prefix; the actual source of truth is Setu's own Postman
  collection ("FIU V2 service - public"), whose underlying JSON was pulled
  directly from https://documenter.gw.postman.com/api/collections/22511424/
  2s9Y5VU4MC (found via the page's own network requests, since the public
  collection viewer UI doesn't render its off-screen sections in the DOM
  until scrolled to, and never got there any other way).
- Auth is a real two-step client-credentials exchange -- NOT direct
  x-client-id/x-client-secret headers on every call (that was this client's
  wrong original assumption, and a legacy misread of a business-logic 401
  along the way; see git history if curious):
    1. POST https://orgservice-prod.setu.co/v1/users/login
       headers: Content-Type: application/json, client: bridge
       body:    {"clientID": ..., "grant_type": "client_credentials", "secret": ...}
       -> {"access_token": "<JWT>", "refresh_token": ""}
       The JWT is short-lived (~30 min, per its own exp/iat claims) --
       this client re-fetches it per process rather than persisting it,
       which is fine for this project's one-shot CLI/API usage but would
       need real token caching/refresh for a long-running production
       service.
    2. Every data-plane call sends `Authorization: Bearer <access_token>`
       + `x-product-instance-id`. (One exception, unused by this client:
       GET /v2/fips takes x-client-id/x-client-secret directly, per the
       same Postman collection -- a genuinely different, simpler-auth
       endpoint, not evidence for the rest.)
- Consent body has an undocumented required field: for consentMode "VIEW"
  (Setu Bridge's default), the API 400s with "datalife value has to be 0"
  unless the body includes `"dataLife": {"unit": "MONTH", "value": "0"}`
  explicitly -- found by reading the live 400 response, not from any doc.
- `vua` must be `<mobile>@<AA handle>` for a real licensed/mock Account
  Aggregator (e.g. `9999999999@onemoney`, Setu's own doc example, confirmed
  live to pass validation). An FIP name like `@setu-fip` is NOT a valid AA
  handle and 400s with "Account Aggregator ... not supported" -- the FIP
  (the actual mock bank, e.g. "Setu FIP-2") is chosen later, inside the
  consent webview, not in this request.
- Setu's data-session API returns already-DECRYPTED FI data (Setu handles
  the AA ecosystem's ECDH key-exchange/decryption on your behalf) -- Setu's
  "Data flow" docs literally label the endpoint "Fetch decrypted FI data"
  and show the webhook payload's FI data under a `decryptedFI` key, already
  plaintext JSON. No crypto needed on our side.
- Sandbox consent approval still requires a human to open `consent.url` and
  click through Setu's mock-FIP webview (there is no headless/API way to
  auto-approve a sandbox consent) -- this is a live protocol interaction,
  not a mock.

Env vars required (see ../.env.example):
  SETU_BASE_URL              https://fiu-sandbox.setu.co (confirmed, sandbox)
  SETU_CLIENT_ID             per-product credential from Bridge Step 2 ("+ Add
                              new" under Testing details -- the org-wide
                              Settings > API keys pair is NOT auto-attached to
                              a product and will 401)
  SETU_CLIENT_SECRET
  SETU_PRODUCT_INSTANCE_ID   from the product's own Step 2 panel, labelled
                              "Use your product ID ... as x-product-instance-id"
                              -- NOT the Product ID shown in Settings/overview
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://orgservice-prod.setu.co/v1/users/login"


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
    """Consent + FI-data-session flow against Setu's AA Gateway V2 API."""

    def __init__(self, config: SetuAAConfig | None = None):
        self.config = config or SetuAAConfig.from_env()
        self._access_token: str | None = None

    def _fetch_access_token(self) -> str:
        """POST /v1/users/login -- client-credentials exchange for a short-lived
        (~30 min) bearer JWT. Re-fetched per client instance, not persisted
        across processes; fine for this project's one-shot CLI/API usage."""
        resp = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/json", "client": "bridge"},
            json={
                "clientID": self.config.client_id,
                "grant_type": "client_credentials",
                "secret": self.config.client_secret,
            },
            timeout=30,
        )
        if not resp.ok:
            raise SetuAAError(f"Setu token exchange failed: {resp.status_code} {resp.text}", resp)
        token = resp.json().get("access_token")
        if not token:
            raise SetuAAError(f"Setu token exchange returned no access_token: {resp.text}", resp)
        return token

    def _headers(self) -> dict[str, str]:
        if self._access_token is None:
            self._access_token = self._fetch_access_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token}",
            "x-product-instance-id": self.config.product_instance_id,
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        resp = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        if resp.status_code == 401 and self._access_token is not None:
            # Bearer token may have expired mid-run (~30 min lifetime) -- refetch once.
            self._access_token = None
            resp = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        if not resp.ok:
            raise SetuAAError(
                f"Setu AA API {method} {path} failed: {resp.status_code} {resp.text}", resp
            )
        return resp.json() if resp.content else {}

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
        """POST /v2/consents -- returns {id, url, status, detail...}.

        `url` is the consent webview link a human must open to approve/reject
        in the sandbox (using a Setu mock FIP test account). `vua` must be
        `<mobile>@<AA handle>` (e.g. "9999999999@onemoney"), NOT an FIP name --
        confirmed live: "@setu-fip" 400s as an unsupported AA handle.
        """
        body: dict[str, Any] = {
            "consentDuration": {"unit": "MONTH", "value": str(duration_months)},
            "vua": vua,
            "context": [],
            # Required for Bridge's default "VIEW" consent mode -- omitting
            # this 400s with "datalife value has to be 0" (found live, not
            # documented anywhere).
            "dataLife": {"unit": "MONTH", "value": "0"},
        }
        if data_range_from and data_range_to:
            body["dataRange"] = {"from": data_range_from, "to": data_range_to}
        if tags:
            # Must match tags pre-configured in the FIU's Bridge product
            # config -- confirmed live: an arbitrary/unconfigured tag 400s
            # with "These tags are not part of your FIU config". No tags
            # are configured for this project's product, so this is only
            # sent when a caller explicitly passes some.
            body["additionalParams"] = {"tags": tags}
        return self._request("POST", "/v2/consents", json=body)

    def get_consent_status(self, consent_id: str, expanded: bool = True) -> dict[str, Any]:
        """GET /v2/consents/:id -- status in {PENDING, ACTIVE, REJECTED, REVOKED, EXPIRED}."""
        params = {"expanded": "true"} if expanded else {}
        return self._request("GET", f"/v2/consents/{consent_id}", params=params)

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
        """POST /v2/sessions -- kicks off data prep at the linked FIP(s)."""
        body = {
            "consentId": consent_id,
            "dataRange": {"from": data_range_from, "to": data_range_to},
            "format": response_format,
        }
        return self._request("POST", "/v2/sessions", json=body)

    def get_data_session(self, session_id: str) -> dict[str, Any]:
        """GET /v2/sessions/:id -- decrypted FI data once ready.

        status: PENDING (not ready) / PARTIAL (some FIPs delivered) /
        COMPLETED (all delivered).
        """
        return self._request("GET", f"/v2/sessions/{session_id}")

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
