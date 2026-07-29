"""Shared Smartlead API client (v1). Uses requests + api_key query param per official docs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://server.smartlead.ai/api/v1"
DEFAULT_TIMEOUT = 60

_SESSION = requests.Session()
_SESSION.trust_env = False  # ignore HTTP_PROXY/HTTPS_PROXY — avoids tunnel 403 on some Macs
_SESSION.headers.update(
    {
        "Accept": "application/json",
        "User-Agent": "LUMO22-smartlead-client/1.0",
    }
)


def load_api_key() -> str:
    load_dotenv(ROOT / ".env")
    return os.getenv("SMARTLEAD_API_KEY", "").strip()


def api_request(
    method: str,
    path: str,
    *,
    api_key: str | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[int, Any]:
    """
    Call Smartlead v1. `path` should start with / e.g. /campaigns/ or /campaigns/123.
    Returns (status_code, parsed_json_or_text).
    """
    key = (api_key or load_api_key()).strip()
    if not key:
        raise ValueError("SMARTLEAD_API_KEY is empty — set it in .env")

    path = path if path.startswith("/") else f"/{path}"
    # Official examples use trailing slash on collection routes.
    if path in ("/campaigns", "/campaigns/"):
        path = "/campaigns/"

    q = {"api_key": key, **(params or {})}
    url = f"{BASE}{path}"

    resp = _SESSION.request(method.upper(), url, params=q, json=json_body, timeout=timeout)
    try:
        data = resp.json()
    except json.JSONDecodeError:
        data = resp.text

    return resp.status_code, data


def safe_error_message(exc: BaseException) -> str:
    """Never echo api_key from failed request URLs."""
    msg = str(exc)
    key = load_api_key()
    if key and key in msg:
        msg = msg.replace(key, "<redacted>")
    return msg


def explain_http_error(status: int, data: Any) -> str:
    if status == 401:
        return (
            "401 Unauthorized — API key invalid, revoked, or not copied in full. "
            "Regenerate in Smartlead → Settings → API and update .env."
        )
    if status == 403:
        return (
            "403 Forbidden — key was sent but Smartlead denied access. Common causes:\n"
            "  • API not activated on your plan (Settings → Activate API, or email support@smartlead.ai)\n"
            "  • Client-level key used for account-level campaign (use main account admin key)\n"
            "  • Campaign ID belongs to a different workspace/client\n"
            "You can still import leads manually in the Smartlead UI."
        )
    if status == 404:
        return "404 Not Found — wrong campaign ID or endpoint path."
    body = data if isinstance(data, str) else json.dumps(data)[:500]
    return f"HTTP {status}: {body}"
