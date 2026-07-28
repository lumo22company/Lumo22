#!/usr/bin/env python3
"""
Apply recommended Cloudflare security settings for lumo22.com.

- SSL mode: strict (or full → strict when origin cert validates)
- Always Use HTTPS: on
- HSTS at edge (30 days; no preload)
- Bot Fight Mode + block AI scrapers (when token has Bot Management permission)
- Ensure www / apex are proxied (orange cloud)

Intentionally DNS-only (do not proxy — breaks email / tracking):
  track.lumo22.com → Smartlead click tracking (open.sleadtrack.com)
  DKIM, _domainconnect, MX, TXT

security.txt is served by the app at /.well-known/security.txt (deploy required).

Opt-in (--origin-guard): Transform Rule stamping a shared secret on proxied requests
so the app can reject direct hits to the Railway origin (see services/origin_guard.py).

Requires in .env:
  CLOUDFLARE_API_TOKEN   — API token for lumo22.com zone
  CLOUDFLARE_ZONE_ID     — optional; looked up if omitted
  ORIGIN_GUARD_SECRET    — only for --origin-guard; same value goes in Railway

Create token: Cloudflare → My Profile → API Tokens → Create Token
  → Edit zone DNS → zone = lumo22.com
  → Zone → SSL and Certificates → Edit
  → Zone → Zone Settings → Edit
  → Zone → Bot Management → Edit   (for Bot Fight Mode)

Manual (not API): Cloudflare account MFA, Turnstile on forms.

Usage:
  python3 scripts/setup_cloudflare_security.py
  python3 scripts/setup_cloudflare_security.py --dry-run
  python3 scripts/setup_cloudflare_security.py --origin-guard --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = "lumo22.com"
WWW = f"www.{DOMAIN}"
CF = "https://api.cloudflare.com/client/v4"

# Origin guard: Transform Rule that stamps a shared secret on every proxied request,
# so the app can reject traffic that reached the Railway origin directly. See services/origin_guard.py.
TRANSFORM_PHASE = "http_request_late_transform"
ORIGIN_GUARD_RULE_DESC = "lumo22 origin guard — stamp shared secret for origin verification"
_RULE_WRITABLE_KEYS = (
    "id",
    "action",
    "action_parameters",
    "expression",
    "description",
    "enabled",
    "logging",
    "ratelimit",
)

# Hostnames that must stay DNS-only (email / domain-connect / tracking)
DNS_ONLY_PREFIXES = (
    "_domainconnect.",
    "s1._domainkey.",
    "s2._domainkey.",
    "track.",
)


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _cf_request(token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{CF}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read())
    if not payload.get("success", True):
        raise RuntimeError(f"Cloudflare API error: {json.dumps(payload)[:800]}")
    return payload


def _zone_id(token: str) -> str:
    zid = _env("CLOUDFLARE_ZONE_ID")
    if zid:
        return zid
    res = _cf_request(token, "GET", f"/zones?name={DOMAIN}")
    zones = res.get("result") or []
    if not zones:
        raise RuntimeError(f"Zone not found for {DOMAIN}")
    return zones[0]["id"]


def _get_setting(token: str, zone_id: str, setting_id: str) -> dict:
    res = _cf_request(token, "GET", f"/zones/{zone_id}/settings/{setting_id}")
    return res.get("result") or {}


def _patch_setting(token: str, zone_id: str, setting_id: str, value) -> dict:
    return _cf_request(
        token,
        "PATCH",
        f"/zones/{zone_id}/settings/{setting_id}",
        {"value": value},
    )


def _dns_records(token: str, zone_id: str, name: str) -> list:
    res = _cf_request(token, "GET", f"/zones/{zone_id}/dns_records?name={name}")
    return res.get("result") or []


def _apply_bot_management(token: str, zone_id: str, *, dry_run: bool = False) -> None:
    """Enable Bot Fight Mode and block AI scrapers when the API token allows it."""
    want = {
        "fight_mode": True,
        "ai_bots_protection": "block",
        "crawler_protection": "enabled",
    }
    try:
        cur = _cf_request(token, "GET", f"/zones/{zone_id}/bot_management")
        have = cur.get("result") or {}
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            print(
                "[skip] bot_management: token lacks Zone → Bot Management → Edit\n"
                "       Add that permission and re-run, or enable Bot Fight Mode in\n"
                "       Cloudflare → Security → Settings → Bot traffic."
            )
            return
        raise

    if all(have.get(k) == v for k, v in want.items()):
        print(f"[ok] bot_management already {want}")
        return
    print(f"[patch] bot_management → {want}")
    if not dry_run:
        _cf_request(token, "PUT", f"/zones/{zone_id}/bot_management", want)
        print("[cloudflare] updated bot_management (Bot Fight Mode + AI bot block)")


def _origin_guard_header() -> str:
    return _env("ORIGIN_GUARD_HEADER") or "X-Origin-Auth"


def _sanitise_rule(rule: dict) -> dict:
    """Drop server-managed fields (version, ref, last_updated) before re-submitting."""
    return {k: v for k, v in rule.items() if k in _RULE_WRITABLE_KEYS}


def _origin_guard_rule(header: str, secret: str) -> dict:
    return {
        "action": "rewrite",
        "action_parameters": {
            "headers": {header: {"operation": "set", "value": secret}}
        },
        "expression": "true",
        "description": ORIGIN_GUARD_RULE_DESC,
        "enabled": True,
    }


def apply_origin_guard(token: str, *, dry_run: bool = False) -> None:
    """
    Install the Transform Rule that stamps ORIGIN_GUARD_SECRET on proxied requests.

    Existing rules in the phase are preserved — only our own rule (matched by
    description) is added or updated.
    """
    secret = _env("ORIGIN_GUARD_SECRET")
    if not secret:
        print(
            "[skip] origin guard: ORIGIN_GUARD_SECRET not in .env\n"
            "       Generate one:  python3 -c \"import secrets; print(secrets.token_urlsafe(32))\"\n"
            "       Add it to .env AND to Railway → Variables (same value), then re-run."
        )
        return

    zone_id = _zone_id(token)
    header = _origin_guard_header()

    try:
        res = _cf_request(
            token, "GET", f"/zones/{zone_id}/rulesets/phases/{TRANSFORM_PHASE}/entrypoint"
        )
        ruleset = res.get("result") or {}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            ruleset = {}  # phase has no ruleset yet; PUT creates it
        elif e.code == 403:
            print(
                "[skip] origin guard: token lacks Zone → Transform Rules → Edit.\n"
                "       Add that permission and re-run."
            )
            return
        else:
            raise

    existing = ruleset.get("rules") or []
    ours = [r for r in existing if r.get("description") == ORIGIN_GUARD_RULE_DESC]
    others = [r for r in existing if r.get("description") != ORIGIN_GUARD_RULE_DESC]

    wanted = _origin_guard_rule(header, secret)
    if len(ours) == 1:
        current = ours[0]
        current_headers = (current.get("action_parameters") or {}).get("headers") or {}
        current_value = (current_headers.get(header) or {}).get("value")
        if current_value == secret and current.get("enabled", True):
            print(f"[ok] origin guard rule already stamps {header} (secret matches .env)")
            return
        print(f"[patch] origin guard rule → refresh {header} value")
        wanted["id"] = current.get("id")
    else:
        print(f"[patch] origin guard rule → add (stamps {header} on all proxied requests)")

    merged = [_sanitise_rule(r) for r in others] + [wanted]
    if others:
        print(f"[note] preserving {len(others)} other rule(s) in {TRANSFORM_PHASE}")

    if dry_run:
        print("[dry-run] no changes written")
        return

    _cf_request(
        token,
        "PUT",
        f"/zones/{zone_id}/rulesets/phases/{TRANSFORM_PHASE}/entrypoint",
        {"rules": merged},
    )
    print(f"[cloudflare] origin guard rule installed ({header})")
    print(
        "\nNext, on the origin (Railway → Variables):\n"
        f"  ORIGIN_GUARD_SECRET = <same value as .env>\n"
        "  ORIGIN_GUARD_MODE   = report        ← log-only; watch deploy logs first\n"
        "Once the logs show no legitimate traffic being flagged, set ORIGIN_GUARD_MODE=enforce.\n"
        "Webhook paths (/webhooks/*) stay exempt in both modes."
    )


def _should_stay_dns_only(name: str) -> bool:
    host = name.rstrip(".")
    if host == DOMAIN or host == WWW:
        return False
    return any(host.startswith(p) for p in DNS_ONLY_PREFIXES) or host.endswith(
        "._domainkey." + DOMAIN
    )


def apply_security(token: str, *, dry_run: bool = False) -> None:
    zone_id = _zone_id(token)
    print(f"[cloudflare] zone_id={zone_id}")

    targets = {
        "always_use_https": "on",
        "min_tls_version": "1.2",
        "security_header": {
            "strict_transport_security": {
                "enabled": True,
                "max_age": 2_592_000,  # 30 days — raise later if happy
                "include_subdomains": False,
                "preload": False,
                "nosniff": True,
            }
        },
    }

    for setting_id, want in targets.items():
        cur = _get_setting(token, zone_id, setting_id)
        have = cur.get("value")
        if have == want:
            print(f"[ok] {setting_id} already {json.dumps(have)}")
            continue
        print(f"[patch] {setting_id}: {json.dumps(have)} → {json.dumps(want)}")
        if not dry_run:
            _patch_setting(token, zone_id, setting_id, want)
            print(f"[cloudflare] updated {setting_id}")

    cur_ssl = _get_setting(token, zone_id, "ssl").get("value")
    if cur_ssl == "strict":
        print(f"[ok] ssl already strict")
    elif cur_ssl == "full":
        print("[patch] ssl: full → strict")
        if not dry_run:
            try:
                _patch_setting(token, zone_id, "ssl", "strict")
                print("[cloudflare] upgraded ssl → strict")
            except urllib.error.HTTPError as e:
                print(f"[note] ssl strict skipped: HTTP {e.code} — keeping full")
    else:
        print(f"[patch] ssl: {cur_ssl!r} → full (then strict)")
        if not dry_run:
            _patch_setting(token, zone_id, "ssl", "full")
            try:
                _patch_setting(token, zone_id, "ssl", "strict")
                print("[cloudflare] upgraded ssl → strict")
            except urllib.error.HTTPError as e:
                print(f"[note] ssl strict skipped: HTTP {e.code} — keeping full")

    _apply_bot_management(token, zone_id, dry_run=dry_run)

    for hostname in (WWW, DOMAIN):
        for rec in _dns_records(token, zone_id, hostname):
            if _should_stay_dns_only(rec.get("name", "")):
                continue
            rtype = rec.get("type")
            if rtype not in ("A", "AAAA", "CNAME"):
                continue
            proxied = rec.get("proxied")
            if proxied:
                print(f"[ok] DNS {rec['name']} ({rtype}) proxied")
                continue
            print(f"[patch] DNS {rec['name']} ({rtype}) → proxied (orange cloud)")
            if not dry_run:
                _cf_request(
                    token,
                    "PATCH",
                    f"/zones/{zone_id}/dns_records/{rec['id']}",
                    {"proxied": True},
                )
                print(f"[cloudflare] proxied {rec['name']}")

    track = _dns_records(token, zone_id, f"track.{DOMAIN}")
    if track:
        print(
            f"\n[note] track.{DOMAIN} stays DNS-only (Smartlead click tracking). "
            "Cloudflare may still flag HSTS/TLS on that hostname — safe to ignore."
        )
    print(
        "\nDone. Deploy app for security.txt. Re-scan Security Insights in ~24h.\n"
        "Manual: enable MFA on your Cloudflare login; Turnstile only if you add forms."
    )


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Print planned changes only")
    ap.add_argument(
        "--origin-guard",
        action="store_true",
        help="Also install the Transform Rule that stamps ORIGIN_GUARD_SECRET (opt-in)",
    )
    args = ap.parse_args()

    token = _env("CLOUDFLARE_API_TOKEN")
    if not token:
        print(
            "Missing CLOUDFLARE_API_TOKEN in .env\n\n"
            "1. Cloudflare → My Profile → API Tokens → Create Token\n"
            "2. Template: Edit zone DNS → zone lumo22.com\n"
            "3. Add: Zone → SSL and Certificates → Edit\n"
            "4. Add: Zone → Zone Settings → Edit\n"
            "5. Add: Zone → Bot Management → Edit\n"
            "6. Add to .env: CLOUDFLARE_API_TOKEN=...\n"
            "7. Re-run: python3 scripts/setup_cloudflare_security.py\n",
            file=sys.stderr,
        )
        sys.exit(1)

    apply_security(token, dry_run=args.dry_run)
    if args.origin_guard:
        print()
        apply_origin_guard(token, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
