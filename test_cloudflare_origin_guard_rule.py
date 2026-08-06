#!/usr/bin/env python3
"""
Tests for the origin-guard Transform Rule writer in scripts/setup_cloudflare_security.py.

Cloudflare's ruleset entrypoint is written with PUT, which REPLACES every rule in
the phase. These tests pin the merge behaviour so the script can never drop rules
it did not create.
Run with: pytest test_cloudflare_origin_guard_rule.py -v
"""
import importlib.util
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "scripts" / "setup_cloudflare_security.py"
SECRET = "s3cret-value"


@pytest.fixture
def cf(monkeypatch):
    """Load the script as a module with Cloudflare API calls recorded, not sent."""
    spec = importlib.util.spec_from_file_location("cf_security", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "_zone_id", lambda token: "zone123")
    monkeypatch.setenv("ORIGIN_GUARD_SECRET", SECRET)
    monkeypatch.delenv("ORIGIN_GUARD_HEADER", raising=False)

    calls = []

    def fake_request(token, method, path, body=None):
        calls.append({"method": method, "path": path, "body": body})
        if method == "GET":
            return {"result": {"rules": fake_request.existing}}
        return {"result": {}}

    fake_request.existing = []
    monkeypatch.setattr(mod, "_cf_request", fake_request)
    mod._calls = calls
    mod._set_existing = lambda rules: setattr(fake_request, "existing", rules)
    return mod


def _put_rules(mod):
    puts = [c for c in mod._calls if c["method"] == "PUT"]
    assert len(puts) == 1, f"expected exactly one PUT, got {len(puts)}"
    return puts[0]["body"]["rules"]


def test_rule_is_added_when_phase_is_empty(cf):
    cf._set_existing([])
    cf.apply_origin_guard("token")

    rules = _put_rules(cf)
    assert len(rules) == 1
    headers = rules[0]["action_parameters"]["headers"]
    assert headers["X-Origin-Auth"] == {"operation": "set", "value": SECRET}
    assert rules[0]["expression"] == "true"


def test_existing_unrelated_rules_are_preserved(cf):
    """A PUT that dropped the user's own Transform Rules would be a silent outage."""
    mine = {
        "id": "rule-abc",
        "description": "customer's own header rewrite",
        "action": "rewrite",
        "expression": 'http.host eq "lumo22.com"',
        "action_parameters": {"headers": {"X-Thing": {"operation": "set", "value": "1"}}},
    }
    cf._set_existing([mine])
    cf.apply_origin_guard("token")

    rules = _put_rules(cf)
    descriptions = [r["description"] for r in rules]
    assert "customer's own header rewrite" in descriptions
    assert cf.ORIGIN_GUARD_RULE_DESC in descriptions
    assert len(rules) == 2


def test_server_managed_fields_are_stripped_from_preserved_rules(cf):
    """version/ref/last_updated are read-only; echoing them back is rejected."""
    cf._set_existing([{
        "id": "rule-abc",
        "version": "3",
        "ref": "rule-abc",
        "last_updated": "2026-01-01T00:00:00Z",
        "description": "other",
        "action": "rewrite",
        "expression": "true",
    }])
    cf.apply_origin_guard("token")

    preserved = [r for r in _put_rules(cf) if r["description"] == "other"][0]
    assert "version" not in preserved
    assert "ref" not in preserved
    assert "last_updated" not in preserved
    assert preserved["id"] == "rule-abc"


def test_rerun_with_same_secret_is_a_noop(cf):
    """Idempotent: nothing is written when the rule already matches."""
    cf._set_existing([{
        "id": "rule-guard",
        "description": cf.ORIGIN_GUARD_RULE_DESC,
        "action": "rewrite",
        "expression": "true",
        "enabled": True,
        "action_parameters": {
            "headers": {"X-Origin-Auth": {"operation": "set", "value": SECRET}}
        },
    }])
    cf.apply_origin_guard("token")

    assert [c for c in cf._calls if c["method"] == "PUT"] == []


def test_rotated_secret_updates_in_place(cf):
    """Changing the secret refreshes the existing rule rather than duplicating it."""
    cf._set_existing([{
        "id": "rule-guard",
        "description": cf.ORIGIN_GUARD_RULE_DESC,
        "action": "rewrite",
        "expression": "true",
        "enabled": True,
        "action_parameters": {
            "headers": {"X-Origin-Auth": {"operation": "set", "value": "old-secret"}}
        },
    }])
    cf.apply_origin_guard("token")

    rules = _put_rules(cf)
    assert len(rules) == 1
    assert rules[0]["id"] == "rule-guard"
    assert rules[0]["action_parameters"]["headers"]["X-Origin-Auth"]["value"] == SECRET


def test_dry_run_writes_nothing(cf):
    cf._set_existing([])
    cf.apply_origin_guard("token", dry_run=True)
    assert [c for c in cf._calls if c["method"] == "PUT"] == []


def test_missing_secret_writes_nothing(cf, monkeypatch):
    """Without ORIGIN_GUARD_SECRET the script must not touch the zone at all."""
    monkeypatch.delenv("ORIGIN_GUARD_SECRET", raising=False)
    cf.apply_origin_guard("token")
    assert cf._calls == []


def test_custom_header_name_is_used(cf, monkeypatch):
    monkeypatch.setenv("ORIGIN_GUARD_HEADER", "X-Lumo-Edge")
    cf._set_existing([])
    cf.apply_origin_guard("token")

    headers = _put_rules(cf)[0]["action_parameters"]["headers"]
    assert "X-Lumo-Edge" in headers
    assert "X-Origin-Auth" not in headers
