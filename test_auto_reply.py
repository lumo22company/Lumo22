#!/usr/bin/env python3
"""
Test auto-reply on/off and skip-reply-domains logic (no DB or email).
Run: python test_auto_reply.py
"""
import sys
# Import the private helpers by running the module and accessing from inbound_reply_service
from services.inbound_reply_service import _sender_domain, _should_skip_reply


def test_sender_domain():
    assert _sender_domain("client@gmail.com") == "gmail.com"
    assert _sender_domain("  Client@Gmail.COM  ") == "gmail.com"
    assert _sender_domain("enquiries@mybusiness.com") == "mybusiness.com"
    assert _sender_domain("") == ""
    assert _sender_domain("no-at-sign") == ""
    assert _sender_domain("a@b.co") == "b.co"
    print("  _sender_domain: OK")


def test_should_skip_reply_auto_off():
    setup = {"auto_reply_enabled": False, "skip_reply_domains": None}
    assert _should_skip_reply(setup, "anyone@example.com") is True
    setup2 = {"auto_reply_enabled": False, "skip_reply_domains": "mybusiness.com"}
    assert _should_skip_reply(setup2, "client@gmail.com") is True
    print("  _should_skip_reply (auto_reply_enabled=False): OK")


def test_should_skip_reply_no_skip_domains():
    setup = {"auto_reply_enabled": True, "skip_reply_domains": None}
    assert _should_skip_reply(setup, "client@gmail.com") is False
    setup2 = {"auto_reply_enabled": True, "skip_reply_domains": ""}
    assert _should_skip_reply(setup2, "client@gmail.com") is False
    print("  _should_skip_reply (no skip_reply_domains): OK")


def test_should_skip_reply_sender_in_skip_list():
    setup = {"auto_reply_enabled": True, "skip_reply_domains": "mybusiness.com"}
    assert _should_skip_reply(setup, "team@mybusiness.com") is True
    assert _should_skip_reply(setup, "me@MYBUSINESS.COM") is True
    assert _should_skip_reply(setup, "client@gmail.com") is False
    print("  _should_skip_reply (sender in skip list): OK")


def test_should_skip_reply_multiple_domains():
    setup = {"auto_reply_enabled": True, "skip_reply_domains": " mybusiness.com , mycompany.co.uk "}
    assert _should_skip_reply(setup, "a@mybusiness.com") is True
    assert _should_skip_reply(setup, "b@mycompany.co.uk") is True
    assert _should_skip_reply(setup, "c@gmail.com") is False
    print("  _should_skip_reply (multiple domains): OK")


def test_should_skip_reply_missing_key_defaults():
    # No auto_reply_enabled key => treat as on (don't skip)
    setup = {}
    assert _should_skip_reply(setup, "x@y.com") is False
    # None for skip_reply_domains
    setup2 = {"auto_reply_enabled": True, "skip_reply_domains": None}
    assert _should_skip_reply(setup2, "x@y.com") is False
    print("  _should_skip_reply (missing keys / defaults): OK")


def main():
    print("Testing auto-reply logic...")
    test_sender_domain()
    test_should_skip_reply_auto_off()
    test_should_skip_reply_no_skip_domains()
    test_should_skip_reply_sender_in_skip_list()
    test_should_skip_reply_multiple_domains()
    test_should_skip_reply_missing_key_defaults()
    print("All tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
