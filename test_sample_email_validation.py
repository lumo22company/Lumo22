#!/usr/bin/env python3
"""Signup-time email checks for the free sample (services/email_validation.py).

The guiding rule is fail-open: these checks catch typos and dead domains, and must
never block a signup because DNS was slow or a resolver was missing.
"""
import sys
import types

from services.email_validation import (
    domain_accepts_mail,
    is_plausible_address,
    suggest_domain_correction,
    validate_signup_email,
)


def test_rejects_only_impossible_addresses():
    for bad in ("", "asdf", "a@b", "sophie@", "@gmail.com", "x y@gmail.com", "a@@b.com"):
        assert not is_plausible_address(bad), f"should reject {bad!r}"
    for good in ("sophie@gmail.com", "a.b+tag@sub.example.co.uk", "x@lumo22.com"):
        assert is_plausible_address(good), f"should accept {good!r}"


def test_suggests_corrections_for_near_miss_domains():
    assert suggest_domain_correction("sophie@gmial.com") == "sophie@gmail.com"
    assert suggest_domain_correction("sophie@gmai.com") == "sophie@gmail.com"
    assert suggest_domain_correction("sophie@outlook.con") == "sophie@outlook.com"
    assert suggest_domain_correction("sophie@hotmial.co.uk") == "sophie@hotmail.co.uk"


def test_never_nags_a_correct_or_unrelated_domain():
    # Already correct — no suggestion.
    assert suggest_domain_correction("sophie@gmail.com") is None
    # A real business domain must not be "corrected" into a consumer one.
    assert suggest_domain_correction("sophie@lumo22.com") is None
    assert suggest_domain_correction("hello@northwindbakery.co.uk") is None


def _install_fake_resolver(behaviour):
    """Swap in a dns.resolver stub so DNS outcomes can be tested without network."""
    dns_mod = types.ModuleType("dns")
    resolver_mod = types.ModuleType("dns.resolver")

    class NXDOMAIN(Exception):
        pass

    class NoAnswer(Exception):
        pass

    class Timeout(Exception):
        pass

    class Resolver:
        timeout = None
        lifetime = None

        def resolve(self, domain, rtype):
            if behaviour == "ok":
                return ["mx1.example.com"]
            if behaviour == "nxdomain":
                raise NXDOMAIN()
            if behaviour == "noanswer":
                raise NoAnswer()
            if behaviour == "timeout":
                raise Timeout()
            raise RuntimeError("unexpected resolver failure")

    resolver_mod.Resolver = Resolver
    resolver_mod.NXDOMAIN = NXDOMAIN
    resolver_mod.NoAnswer = NoAnswer
    dns_mod.resolver = resolver_mod
    sys.modules["dns"] = dns_mod
    sys.modules["dns.resolver"] = resolver_mod


def _clear_fake_resolver():
    sys.modules.pop("dns", None)
    sys.modules.pop("dns.resolver", None)


def test_dns_outcomes_map_to_allow_or_block():
    try:
        # Only a definitive "this domain cannot receive mail" blocks.
        _install_fake_resolver("ok")
        assert domain_accepts_mail("example.com") is True
        _install_fake_resolver("nxdomain")
        assert domain_accepts_mail("example.com") is False
        _install_fake_resolver("noanswer")
        assert domain_accepts_mail("example.com") is False
        # Everything inconclusive fails open.
        _install_fake_resolver("timeout")
        assert domain_accepts_mail("example.com") is None
        _install_fake_resolver("other")
        assert domain_accepts_mail("example.com") is None
    finally:
        _clear_fake_resolver()


def test_missing_resolver_library_fails_open():
    """No dnspython installed must not block signups."""
    _clear_fake_resolver()
    sys.modules["dns"] = None  # import dns.resolver -> ImportError
    try:
        assert domain_accepts_mail("example.com") is None
        ok, err, _ = validate_signup_email("sophie@some-unresolvable-domain-xyz.com")
        assert ok and err is None
    finally:
        _clear_fake_resolver()


def test_dead_domain_is_blocked_but_override_lets_the_user_through():
    """A rejection must never be a dead end."""
    try:
        _install_fake_resolver("nxdomain")
        ok, err, _ = validate_signup_email("sophie@definitely-not-real-xyz.com")
        assert not ok and err
        # Second pass: the user confirmed the address is right.
        ok2, err2, _ = validate_signup_email(
            "sophie@definitely-not-real-xyz.com", allow_override=True
        )
        assert ok2 and err2 is None
    finally:
        _clear_fake_resolver()


def test_typo_domain_that_resolves_still_returns_a_suggestion():
    """Typosquats usually have MX records, so a clean DNS result is not enough."""
    try:
        _install_fake_resolver("ok")
        ok, err, suggestion = validate_signup_email("sophie@gmial.com")
        assert ok and err is None
        assert suggestion == "sophie@gmail.com"
    finally:
        _clear_fake_resolver()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("All sample email validation tests passed.")
