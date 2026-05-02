#!/usr/bin/env python3
"""
Test script to verify the system is working correctly (Captions-focused).
Run this after setting up your API keys.
"""
import sys
import os

import pytest
from dotenv import load_dotenv

load_dotenv()


def test_imports():
    """Test that required packages are installed."""
    print("Testing imports...")
    try:
        import flask  # noqa: F401
        import supabase  # noqa: F401
    except ImportError as e:
        raise AssertionError(f"Import error: {e}") from e
    print("✅ All packages imported successfully")


def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    from config import Config

    issues = []

    if not Config.SUPABASE_URL or "your-project" in (Config.SUPABASE_URL or ""):
        issues.append("SUPABASE_URL not configured")
    else:
        print("✅ Supabase URL configured")

    if not Config.SUPABASE_KEY or "your-supabase" in (Config.SUPABASE_KEY or ""):
        issues.append("SUPABASE_KEY not configured")
    else:
        print("✅ Supabase key configured")

    assert not issues, f"Configuration issues: {', '.join(issues)}"


@pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS", "").lower() == "true"
    or (os.getenv("SUPABASE_KEY") or "").strip() == "ci-placeholder-key"
    or "example.supabase.co" in (os.getenv("SUPABASE_URL") or ""),
    reason="GitHub Actions / CI uses placeholder Supabase; run this test locally with a real project.",
)
def test_supabase():
    """Test Supabase connection via caption order service."""
    print("\nTesting Supabase connection...")
    try:
        from services.caption_order_service import CaptionOrderService

        svc = CaptionOrderService()
        # Light query that doesn't depend on existing data
        orders = svc.get_awaiting_intake_orders()
        print(f"✅ Supabase connected! (caption_orders accessible, {len(orders)} awaiting intake)")
    except Exception as e:
        raise AssertionError(
            f"Supabase test failed: {e}. Ensure SUPABASE_URL and SUPABASE_KEY are correct and "
            "caption_orders exists."
        ) from e


def main():
    """Run all tests."""
    print("=" * 60)
    print("SYSTEM TEST SUITE (Captions)")
    print("=" * 60)
    print()

    tests = [
        ("Package Imports", test_imports),
        ("Configuration", test_config),
    ]

    if os.getenv("SUPABASE_URL") and "your-project" not in (os.getenv("SUPABASE_URL") or ""):
        if os.getenv("SUPABASE_KEY") and "your-supabase" not in (os.getenv("SUPABASE_KEY") or ""):
            tests.append(("Supabase Database", test_supabase))

    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, True))
        except AssertionError as e:
            print(f"❌ {name}: {e}")
            results.append((name, False))
        except Exception as e:
            print(f"❌ {name} test crashed: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Your system is ready to use.")
        print("   Run: python app.py")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
