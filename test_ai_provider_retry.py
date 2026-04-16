#!/usr/bin/env python3
"""Tests for transient AI provider retries in services/ai_provider.py."""
from unittest.mock import MagicMock, patch

import httpx


def test_anthropic_retries_on_529_then_succeeds():
    from anthropic import APIStatusError

    import services.ai_provider as ap

    r529 = httpx.Response(529, request=httpx.Request("POST", "https://api.anthropic.com"))
    err = APIStatusError("overloaded", response=r529, body=None)

    ok_block = MagicMock()
    ok_block.text = "success-body"
    resp_ok = MagicMock()
    resp_ok.content = [ok_block]

    with (
        patch.object(ap.Config, "AI_PROVIDER", "anthropic"),
        patch.object(ap.Config, "ANTHROPIC_API_KEY", "sk-ant-test"),
        patch.object(ap.Config, "ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
        patch("anthropic.Anthropic") as mock_anthropic,
        patch.object(ap, "time") as mock_time,
    ):
        mock_time.sleep = MagicMock()
        inst = mock_anthropic.return_value
        inst.messages.create.side_effect = [err, resp_ok]

        out = ap.chat_completion("system", "user", max_tokens=50)

    assert out == "success-body"
    assert inst.messages.create.call_count == 2
    assert mock_time.sleep.call_count >= 1


def test_openai_does_not_retry_on_400():
    import openai

    import services.ai_provider as ap

    r400 = httpx.Response(400, request=httpx.Request("POST", "https://api.openai.com"))
    err = openai.BadRequestError("bad", response=r400, body=None)

    with (
        patch.object(ap.Config, "AI_PROVIDER", "openai"),
        patch.object(ap.Config, "OPENAI_API_KEY", "sk-test"),
        patch.object(ap.Config, "OPENAI_MODEL", "gpt-4o-mini"),
        patch("openai.OpenAI") as mock_openai,
    ):
        inst = mock_openai.return_value
        inst.chat.completions.create.side_effect = err
        try:
            ap.chat_completion("s", "u", max_tokens=10)
        except openai.BadRequestError:
            pass
        else:
            raise AssertionError("expected BadRequestError")
        assert inst.chat.completions.create.call_count == 1


if __name__ == "__main__":
    test_anthropic_retries_on_529_then_succeeds()
    test_openai_does_not_retry_on_400()
    print("OK")
