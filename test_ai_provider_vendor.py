#!/usr/bin/env python3
"""Tests for optional AI_VENDOR and log_ai_provider_summary (no full app import)."""
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch


def test_vendor_match_no_warning():
    from config import Config

    with patch.dict(
        os.environ,
        {"AI_PROVIDER": "anthropic", "AI_VENDOR": "anthropic"},
        clear=False,
    ):
        buf = StringIO()
        with redirect_stderr(buf):
            Config.validate_ai_vendor_optional()
        assert not buf.getvalue().strip(), f"expected no stderr, got: {buf.getvalue()!r}"
    print("PASS: AI_VENDOR matches AI_PROVIDER (no warning)")


def test_vendor_mismatch_warns():
    from config import Config

    with patch.dict(
        os.environ,
        {"AI_PROVIDER": "anthropic", "AI_VENDOR": "openai"},
        clear=False,
    ):
        buf = StringIO()
        with redirect_stderr(buf):
            Config.validate_ai_vendor_optional()
        err = buf.getvalue()
        assert "WARNING" in err and "AI_VENDOR" in err, f"expected WARNING, got: {err!r}"
    print("PASS: AI_VENDOR mismatch logs WARNING")


def test_vendor_invalid_ignored_with_warning():
    from config import Config

    with patch.dict(
        os.environ,
        {"AI_PROVIDER": "anthropic", "AI_VENDOR": "maybe-openai"},
        clear=False,
    ):
        buf = StringIO()
        with redirect_stderr(buf):
            Config.validate_ai_vendor_optional()
        assert "WARNING" in buf.getvalue()
    print("PASS: invalid AI_VENDOR logs WARNING and is ignored")


def test_log_summary_contains_effective():
    from config import Config

    with patch.dict(
        os.environ,
        {
            "AI_PROVIDER": "anthropic",
            "AI_VENDOR": "anthropic",
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "OPENAI_API_KEY": "",
        },
        clear=False,
    ):
        buf = StringIO()
        with redirect_stdout(buf):
            Config.log_ai_provider_summary()
        out = buf.getvalue()
        assert "effective=" in out and "anthropic" in out
        assert "ANTHROPIC_API_KEY set=True" in out
        assert "OPENAI_API_KEY set=False" in out
    print("PASS: log_ai_provider_summary line shape")


def main():
    test_vendor_match_no_warning()
    test_vendor_mismatch_warns()
    test_vendor_invalid_ignored_with_warning()
    test_log_summary_contains_effective()
    print("\nAll AI_VENDOR / summary tests passed.")


if __name__ == "__main__":
    main()
