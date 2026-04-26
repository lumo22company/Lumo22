"""Pytest root config: disable CSRF so test_client POSTs do not need tokens."""
import os

os.environ.setdefault("DISABLE_CSRF", "1")
