#!/usr/bin/env python3
"""
Check production-oriented config using the same rules as the live app (Config.validate).

Usage (from repo root, with the same env as Railway or a copied .env):

  # Full production validation (requires all production secrets in the environment)
  FLASK_ENV=production python scripts/verify_security_privacy_readiness.py

Does not print secret values. Does not connect to Stripe/Supabase except what
validate() implies (it only checks env presence, not network).

Exit code 0 = validation passed; non-zero = fix the printed variable names in Railway.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(repo_root, ".env"))
    except ImportError:
        pass

    if (os.getenv("FLASK_ENV") or "").strip().lower() != "production" and not (
        (os.getenv("SECRET_KEY") or "").strip()
        and (os.getenv("SECRET_KEY") or "").strip() != "dev-secret-key-change-in-production"
    ):
        print(
            "Tip: set FLASK_ENV=production (recommended) or set SECRET_KEY to a non-default\n"
            "      value so production checks run. Example:\n"
            "        FLASK_ENV=production python scripts/verify_security_privacy_readiness.py",
            file=sys.stderr,
        )
        print("Running with current environment; is_production() may be false — checks are looser.\n")

    try:
        from config import Config

        Config.validate()
        Config.validate_ai_vendor_optional()
    except ValueError as e:
        print("Configuration check failed:\n", e, file=sys.stderr)
        print("\nSee PRODUCTION_ENV_SETUP.md and set missing variables in Railway.", file=sys.stderr)
        return 1
    except Exception as e:
        print("Unexpected error during validation:", e, file=sys.stderr)
        return 1

    print("OK — Config.validate() passed for this environment.")
    if Config.is_production():
        base = (Config.BASE_URL or "").strip()
        if not base.lower().startswith("https://"):
            print(
                "Warning: BASE_URL should normally start with https:// in production.",
                file=sys.stderr,
            )
        if (os.getenv("FLASK_DEBUG") or "").lower() in ("1", "true", "yes"):
            print(
                "Warning: FLASK_DEBUG should be False in production.",
                file=sys.stderr,
            )
        if not (getattr(Config, "CRON_SECRET", None) or "").strip():
            print(
                "Note: CRON_SECRET is unset. Required if you call /api/captions-send-reminders from a scheduler.",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
