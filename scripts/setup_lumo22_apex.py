#!/usr/bin/env python3
"""
Fix https://lumo22.com (apex) when www already works on Railway + Cloudflare.

Two modes (tries both when tokens are set):

A) Cloudflare redirect (recommended, fast): lumo22.com → www.lumo22.com at the edge.
   Needs: CLOUDFLARE_API_TOKEN

B) Railway custom domain: register lumo22.com on Railway + _railway-verify TXT in Cloudflare.
   Needs: RAILWAY_TOKEN, CLOUDFLARE_API_TOKEN, RAILWAY_SERVICE_ID

Get Cloudflare token: Dashboard → My Profile → API Tokens → Create Token
  → Edit zone DNS template → zone lumo22.com

Get Railway token: Railway → Account/Project Settings → Tokens

Usage:
  python3 scripts/setup_lumo22_apex.py
  python3 scripts/setup_lumo22_apex.py --redirect-only
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
RAILWAY_TARGET = "lumo-22-production.up.railway.app"
GRAPHQL = "https://backboard.railway.com/graphql/v2"
CF = "https://api.cloudflare.com/client/v4"


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
        raise RuntimeError(f"Cloudflare API error: {json.dumps(payload)[:500]}")
    return payload


def _cf_zone_id(token: str) -> str:
    zid = _env("CLOUDFLARE_ZONE_ID")
    if zid:
        return zid
    res = _cf_request(token, "GET", f"/zones?name={DOMAIN}")
    zones = res.get("result") or []
    if not zones:
        raise RuntimeError(f"Cloudflare zone not found for {DOMAIN}")
    return zones[0]["id"]


def setup_cloudflare_redirect(token: str) -> None:
    zone_id = _cf_zone_id(token)
    print(f"[cloudflare] zone_id={zone_id}")

    # Fetch existing dynamic redirect ruleset entrypoint (if any)
    try:
        existing = _cf_request(
            token,
            "GET",
            f"/zones/{zone_id}/rulesets/phases/http_request_dynamic_redirect/entrypoint",
        )
        ruleset = existing.get("result") or {}
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        ruleset = {}

    rule = {
        "expression": f'(http.host eq "{DOMAIN}")',
        "description": "Redirect apex to www (Lumo 22)",
        "action": "redirect",
        "action_parameters": {
            "from_value": {
                "status_code": 301,
                "target_url": {
                    "expression": f'concat("https://{WWW}", http.request.uri.path)',
                },
                "preserve_query_string": True,
            }
        },
    }

    rules = [r for r in (ruleset.get("rules") or []) if r.get("description") != rule["description"]]
    rules.insert(0, rule)

    body = {
        "name": ruleset.get("name") or "default",
        "kind": "zone",
        "phase": "http_request_dynamic_redirect",
        "rules": rules,
    }

    if ruleset.get("id"):
        _cf_request(token, "PUT", f"/zones/{zone_id}/rulesets/{ruleset['id']}", body)
        print(f"[cloudflare] updated redirect ruleset {ruleset['id']}")
    else:
        res = _cf_request(
            token,
            "POST",
            f"/zones/{zone_id}/rulesets/phases/http_request_dynamic_redirect/entrypoint",
            body,
        )
        print(f"[cloudflare] created redirect ruleset {res.get('result', {}).get('id')}")

    print(f"[cloudflare] {DOMAIN} → https://{WWW} (301)")


def _railway_graphql(token: str, query: str, variables: dict) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        GRAPHQL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    if data.get("errors"):
        raise RuntimeError(f"Railway GraphQL: {data['errors']}")
    return data.get("data") or {}


def setup_railway_custom_domain(railway_token: str, service_id: str, cf_token: str) -> None:
    mutation = """
    mutation customDomainCreate($input: CustomDomainCreateInput!) {
      customDomainCreate(input: $input) {
        id
        domain
        status {
          dnsRecords { fqdn type value status }
          verificationToken
          certificateStatus
        }
      }
    }
    """
    data = _railway_graphql(
        railway_token,
        mutation,
        {"input": {"serviceId": service_id, "domain": DOMAIN}},
    )
    cd = data.get("customDomainCreate") or {}
    if not cd:
        raise RuntimeError("Railway customDomainCreate returned empty")
    print(f"[railway] added custom domain {cd.get('domain')} id={cd.get('id')}")

    verify_token = (cd.get("status") or {}).get("verificationToken")
    if not verify_token:
        print("[railway] no verificationToken yet — check Railway dashboard DNS panel")
        return

    zone_id = _cf_zone_id(cf_token)
    txt_name = f"_railway-verify.{DOMAIN}"
    _cf_request(
        cf_token,
        "POST",
        f"/zones/{zone_id}/dns_records",
        {
            "type": "TXT",
            "name": txt_name,
            "content": verify_token,
            "ttl": 1,
        },
    )
    print(f"[cloudflare] added TXT {txt_name}")

    # Ensure apex CNAME to Railway (Cloudflare supports CNAME flattening on apex)
    records = _cf_request(
        cf_token,
        "GET",
        f"/zones/{zone_id}/dns_records?type=CNAME&name={DOMAIN}",
    ).get("result") or []
    if not any(RAILWAY_TARGET in (r.get("content") or "") for r in records):
        _cf_request(
            cf_token,
            "POST",
            f"/zones/{zone_id}/dns_records",
            {
                "type": "CNAME",
                "name": DOMAIN,
                "content": RAILWAY_TARGET,
                "proxied": True,
                "ttl": 1,
            },
        )
        print(f"[cloudflare] added CNAME @ → {RAILWAY_TARGET}")
    else:
        print("[cloudflare] apex CNAME to Railway already present")


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--redirect-only", action="store_true", help="Only add Cloudflare apex→www redirect")
    args = ap.parse_args()

    cf_token = _env("CLOUDFLARE_API_TOKEN") or _env("CF_API_TOKEN")
    railway_token = _env("RAILWAY_TOKEN") or _env("RAILWAY_API_TOKEN")
    service_id = _env("RAILWAY_SERVICE_ID")

    if not cf_token:
        raise SystemExit(
            "Missing CLOUDFLARE_API_TOKEN in .env\n"
            "Create one: Cloudflare → My Profile → API Tokens → Edit zone DNS (lumo22.com)"
        )

    setup_cloudflare_redirect(cf_token)

    if args.redirect_only:
        return

    if railway_token and service_id:
        setup_railway_custom_domain(railway_token, service_id, cf_token)
    else:
        print(
            "[skip] Railway custom domain — set RAILWAY_TOKEN + RAILWAY_SERVICE_ID in .env "
            "if you want apex to serve directly (redirect-only is enough for most cases)."
        )


if __name__ == "__main__":
    main()
