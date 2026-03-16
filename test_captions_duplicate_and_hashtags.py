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
    if missing:
        print(f"FAIL: Hashtag prompt missing: {missing}")
        return False
    print("OK: Hashtag prompt contains required language")
    return True


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
    if missing:
        print(f"FAIL: Duplicate guard missing: {missing}")
        return False
    print("OK: Duplicate delivery guard in place")
    return True


def main():
    ok1 = test_hashtag_prompt()
    ok2 = test_duplicate_guard()
    print("-" * 50)
    if ok1 and ok2:
        print("All verification checks passed.")
        sys.exit(0)
    print("Some checks failed.")
    sys.exit(1)


if __name__ == "__main__":
    main()
