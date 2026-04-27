"""Pytest root config: disable CSRF so test_client POSTs do not need tokens."""
import os

import pytest

os.environ.setdefault("DISABLE_CSRF", "1")


@pytest.fixture(autouse=True)
def suppress_ops_alert_emails_in_webhook_tests(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    """
    Prevent local webhook regression tests from sending real ops alert emails.
    Keeps behavior assertions intact while making local test runs side-effect free.
    """
    filename = request.node.fspath.basename
    if not filename.startswith("test_webhook"):
        return

    from services.notifications import NotificationService

    def _noop_alert(*args, **kwargs):
        return True

    for attr in dir(NotificationService):
        if attr.startswith("send_") and attr.endswith("_alert"):
            fn = getattr(NotificationService, attr, None)
            if callable(fn):
                monkeypatch.setattr(NotificationService, attr, _noop_alert)
