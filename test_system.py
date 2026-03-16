#!/usr/bin/env python3
"""
Test script to verify the system is working correctly (Captions-focused).
Run this after setting up your API keys.
"""
import sys
import os
from dotenv import load_dotenv

load_dotenv()


def test_imports():
    """Test that required packages are installed."""
    print("Testing imports...")
    try:
        import flask
        import supabase
        print("✅ All packages imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


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

    if issues:
        print(f"\n⚠️  Configuration issues: {', '.join(issues)}")
        return False

    return True


def test_supabase():
    """Test Supabase connection via caption order service."""
    print("\nTesting Supabase connection...")
    try:
        from services.caption_order_service import CaptionOrderService

        svc = CaptionOrderService()
        # Light query that doesn't depend on existing data
        orders = svc.get_awaiting_intake_orders()
        print(f"✅ Supabase connected! (caption_orders accessible, {len(orders)} awaiting intake)")
        return True
    except Exception as e:
        print(f"❌ Supabase test failed: {e}")
        print("   Make sure:")
        print("   1. SUPABASE_URL and SUPABASE_KEY are correct")
        print("   2. The caption_orders table exists")
        return False


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
            result = test_func()
            results.append((name, result))
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
