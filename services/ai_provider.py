"""
Unified AI provider for chat completions.
Supports OpenAI and Anthropic Claude. Switch via AI_PROVIDER env var.
"""
import random
import time
from typing import Callable, Optional, TypeVar

from config import Config

# Transient HTTP statuses worth a short backoff retry (provider load / blips).
_RETRYABLE_HTTP = frozenset({408, 429, 500, 502, 503, 504, 529})
_MAX_PROVIDER_ATTEMPTS = 3

T = TypeVar("T")


def _retry_after_seconds(exc: BaseException) -> Optional[float]:
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    headers = getattr(resp, "headers", None)
    if not headers:
        return None
    h = headers.get("retry-after") or headers.get("Retry-After")
    if not h:
        return None
    try:
        return float(h)
    except (TypeError, ValueError):
        return None


def _http_status(exc: BaseException) -> Optional[int]:
    resp = getattr(exc, "response", None)
    if resp is not None:
        sc = getattr(resp, "status_code", None)
        if sc is not None:
            return int(sc)
    sc = getattr(exc, "status_code", None)
    if sc is not None:
        return int(sc)
    return None


def _is_retryable_provider_error(exc: BaseException) -> bool:
    import anthropic
    import openai

    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError)):
        return True
    if isinstance(exc, (anthropic.RateLimitError, openai.RateLimitError)):
        return True
    if isinstance(exc, (anthropic.InternalServerError, openai.InternalServerError)):
        return True
    if isinstance(exc, (anthropic.APIStatusError, openai.APIStatusError)):
        sc = _http_status(exc)
        return sc is not None and sc in _RETRYABLE_HTTP
    return False


def _sleep_before_retry(attempt_index: int, exc: BaseException) -> None:
    """attempt_index: 0 before first retry, 1 before second, …"""
    backoff = min(0.75 * (2**attempt_index) + random.uniform(0, 0.55), 22.0)
    ra = _retry_after_seconds(exc)
    if ra is not None and ra > 0:
        backoff = max(backoff, min(ra, 45.0))
    time.sleep(backoff)


def _call_with_provider_retries(fn: Callable[[], T], *, label: str) -> T:
    for attempt in range(_MAX_PROVIDER_ATTEMPTS):
        try:
            return fn()
        except Exception as e:
            if attempt >= _MAX_PROVIDER_ATTEMPTS - 1 or not _is_retryable_provider_error(e):
                raise
            sc = _http_status(e)
            sc_part = f" status={sc}" if sc is not None else ""
            print(
                f"[ai_provider] {label} transient error {type(e).__name__}{sc_part}; "
                f"retry {attempt + 1}/{_MAX_PROVIDER_ATTEMPTS - 1} after backoff"
            )
            _sleep_before_retry(attempt, e)


def chat_completion(
    system: str,
    user: str,
    temperature: float = 0.6,
    max_tokens: int = 4000,
) -> str:
    """
    Call the configured AI provider. Returns the assistant's text content.
    Raises on API error.
    """
    provider = (Config.AI_PROVIDER or "openai").strip().lower()

    if provider == "anthropic":
        return _anthropic_completion(system=system, user=user, temperature=temperature, max_tokens=max_tokens)
    return _openai_completion(system=system, user=user, temperature=temperature, max_tokens=max_tokens)


def _openai_completion(system: str, user: str, temperature: float, max_tokens: int) -> str:
    from openai import OpenAI

    if not Config.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not configured (required when AI_PROVIDER=openai)")
    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    def _do() -> str:
        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()

    return _call_with_provider_retries(_do, label="openai")


def _anthropic_completion(system: str, user: str, temperature: float, max_tokens: int) -> str:
    from anthropic import Anthropic

    if not Config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not configured (required when AI_PROVIDER=anthropic)")
    client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    def _do() -> str:
        response = client.messages.create(
            model=Config.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=max(0.0, min(1.0, temperature)),  # Anthropic expects 0–1
        )
        if not response.content:
            return ""
        parts: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return ("".join(parts) or "").strip()

    return _call_with_provider_retries(_do, label="anthropic")
