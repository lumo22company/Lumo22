"""
WebAuthn (passkey) relying-party settings derived from BASE_URL and optional env overrides.
"""
from __future__ import annotations

import os
from typing import List, Tuple
from urllib.parse import urlparse

from config import Config


def get_webauthn_settings() -> Tuple[str, str, List[str]]:
    """
    Returns (rp_id, rp_name, expected_origins).

    rp_id defaults to registrable host (strips leading www.).
    expected_origins defaults to BASE_URL origin plus a sensible www/non-www sibling when applicable.
    """
    base = (getattr(Config, "BASE_URL", None) or "").strip()
    if not base:
        base = "http://localhost:5001"
    if not base.startswith(("http://", "https://")):
        base = "https://" + base.lstrip("/")

    parsed = urlparse(base)
    host = (parsed.hostname or "localhost").lower()
    netloc = parsed.netloc or host

    default_rp = host[4:] if host.startswith("www.") else host
    rp_id = (os.getenv("WEBAUTHN_RP_ID") or "").strip().lower() or default_rp
    rp_name = (os.getenv("WEBAUTHN_RP_NAME") or "Lumo 22").strip() or "Lumo 22"

    origins_env = (os.getenv("WEBAUTHN_ORIGINS") or "").strip()
    if origins_env:
        origins = [o.strip().rstrip("/") for o in origins_env.split(",") if o.strip()]
    else:
        primary = f"{parsed.scheme}://{netloc}".rstrip("/")
        origins = [primary]
        if host.startswith("www.") and host.count(".") >= 2:
            bare = f"{parsed.scheme}://{host[4:]}"
            if bare not in origins:
                origins.append(bare.rstrip("/"))
        elif not host.startswith("www.") and "." in host and host != "localhost":
            www = f"{parsed.scheme}://www.{host}"
            if www not in origins:
                origins.append(www.rstrip("/"))

    return rp_id, rp_name, origins
