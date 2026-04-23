#!/usr/bin/env python3
"""
Verify duplicate delivery guard and hashtag prompt are in place.
Run: python3 test_captions_duplicate_and_hashtags.py
"""
import sys


def test_hashtag_prompt():
    """Ensure caption generator system prompt requires hashtags on every caption when requested."""
    from services.caption_generator import _build_system_prompt
    prompt = _build_system_prompt({"caption_language": "English (UK)"})
    required = [
        "Every single caption MUST include",
        "Never omit hashtags",
        "**Hashtags:**",
    ]
    missing = [r for r in required if r not in prompt]
    assert not missing, f"Hashtag prompt missing: {missing}"
    print("OK: Hashtag prompt contains required language")


def test_duplicate_guard():
    """Ensure captions_routes has duplicate delivery guard (status check before generation)."""
    import inspect
    from api.captions_routes import _run_generation_and_deliver
    source = inspect.getsource(_run_generation_and_deliver)
    required = [
        'status == "delivered"',
        'status == "generating"',
        "skipping duplicate",
    ]
    missing = [r for r in required if r not in source]
    assert not missing, f"Duplicate guard missing: {missing}"
    print("OK: Duplicate delivery guard in place")


def main():
    print("-" * 50)
    try:
        test_hashtag_prompt()
        test_duplicate_guard()
    except AssertionError as e:
        print(f"Some checks failed: {e}")
        sys.exit(1)
    print("All verification checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
