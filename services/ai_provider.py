"""
Unified AI provider for chat completions.
Supports OpenAI and Anthropic Claude. Switch via AI_PROVIDER env var.
"""
from typing import Optional
from config import Config


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


def _anthropic_completion(system: str, user: str, temperature: float, max_tokens: int) -> str:
    from anthropic import Anthropic
    if not Config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not configured (required when AI_PROVIDER=anthropic)")
    client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    # Same effective config as OpenAI: system + user, temperature, max_tokens
    response = client.messages.create(
        model=Config.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        temperature=max(0.0, min(1.0, temperature)),  # Anthropic expects 0–1
    )
    # Concatenate all text blocks (same as OpenAI's single content string; avoids losing content)
    if not response.content:
        return ""
    parts = []
    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return ("".join(parts) or "").strip()
