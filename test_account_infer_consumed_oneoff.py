#!/usr/bin/env python3
"""Tests for _infer_consumed_oneoff_tokens (hide consumed one-off when upgraded_from_token missing on sub row)."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _base():
    return {
        "intake": {"business_name": "Harbour and Hearth"},
        "created_at": "2026-01-01T00:00:00+00:00",
        "status": "delivered",
    }


def test_infer_when_sub_row_has_no_business_name_in_db():
    """Merge skips without upgraded_from_token; sub intake empty but one-off has name — still infer."""
    from app import _infer_consumed_oneoff_tokens

    one_off = {
        "intake": {"business_name": "Harbour & Hearth"},
        "created_at": "2026-01-01T00:00:00+00:00",
        "status": "delivered",
        "token": "tok-oneoff",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": None,
    }
    sub_cancelled = {
        "intake": None,
        "created_at": "2026-02-01T00:00:00+00:00",
        "status": "delivered",
        "token": "tok-sub",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": "2026-04-09T12:00:00+00:00",
        "upgraded_from_token": None,
    }
    out = _infer_consumed_oneoff_tokens([one_off, sub_cancelled], set())
    assert "tok-oneoff" in out


def test_infer_ampersand_matches_and_in_business_name():
    """One-off 'Harbour & Hearth' pairs with sub 'Harbour and Hearth' after merge/checkout."""
    from app import _infer_consumed_oneoff_tokens

    one_off = {
        "intake": {"business_name": "Harbour & Hearth"},
        "created_at": "2026-01-01T00:00:00+00:00",
        "status": "delivered",
        "token": "tok-oneoff",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": None,
    }
    sub_cancelled = {
        "intake": {"business_name": "Harbour and Hearth"},
        "created_at": "2026-02-01T00:00:00+00:00",
        "status": "delivered",
        "token": "tok-sub",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": "2026-04-09T12:00:00+00:00",
        "upgraded_from_token": None,
    }
    out = _infer_consumed_oneoff_tokens([one_off, sub_cancelled], set())
    assert "tok-oneoff" in out


def test_infer_when_sub_missing_upgraded_from_token():
    from app import _infer_consumed_oneoff_tokens

    one_off = {
        **_base(),
        "token": "tok-oneoff",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": None,
    }
    sub_cancelled = {
        **_base(),
        "token": "tok-sub",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": "2026-04-09T12:00:00+00:00",
        "upgraded_from_token": None,
        "created_at": "2026-02-01T00:00:00+00:00",
    }
    out = _infer_consumed_oneoff_tokens([one_off, sub_cancelled], set())
    assert "tok-oneoff" in out


def test_no_infer_when_upgraded_from_already_in_db():
    from app import _infer_consumed_oneoff_tokens

    one_off = {
        **_base(),
        "token": "tok-a",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": None,
    }
    sub_cancelled = {
        **_base(),
        "token": "tok-b",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": "2026-04-09T12:00:00+00:00",
        "upgraded_from_token": "tok-a",
        "created_at": "2026-02-01T00:00:00+00:00",
    }
    existing = {"tok-a"}
    out = _infer_consumed_oneoff_tokens([one_off, sub_cancelled], existing)
    assert out == set()


def test_no_infer_when_two_former_subs_same_business():
    from app import _infer_consumed_oneoff_tokens

    one_off = {
        **_base(),
        "token": "tok-o",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": None,
    }
    sub1 = {
        **_base(),
        "token": "tok-s1",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": "2026-03-01T00:00:00+00:00",
        "upgraded_from_token": None,
        "created_at": "2026-02-01T00:00:00+00:00",
    }
    sub2 = {
        **_base(),
        "token": "tok-s2",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": "2026-05-01T00:00:00+00:00",
        "upgraded_from_token": None,
        "created_at": "2026-04-01T00:00:00+00:00",
    }
    out = _infer_consumed_oneoff_tokens([one_off, sub1, sub2], set())
    assert "tok-o" not in out


def test_no_infer_when_second_oneoff_between():
    from app import _infer_consumed_oneoff_tokens

    one_off1 = {
        **_base(),
        "token": "tok-o1",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": None,
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    one_off2 = {
        **_base(),
        "token": "tok-o2",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": None,
        "created_at": "2026-02-15T00:00:00+00:00",
    }
    sub_cancelled = {
        **_base(),
        "token": "tok-sub",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": "2026-04-09T12:00:00+00:00",
        "upgraded_from_token": None,
        "created_at": "2026-03-01T00:00:00+00:00",
    }
    out = _infer_consumed_oneoff_tokens([one_off1, one_off2, sub_cancelled], set())
    # First one-off is not consumed: another one-off for the same business sits between it and the sub.
    assert "tok-o1" not in out
    # The later one-off may still be inferred as the unambiguous predecessor to the sub (edge case).


def test_one_off_eligible_former_sub_even_if_awaiting_intake():
    """Cancelled-in-Stripe row must appear under resubscribe even if status is awaiting_intake."""
    from app import _one_off_eligible_for_upgrade_base_dropdown

    row = {
        "stripe_subscription_id": None,
        "subscription_cancelled_at": None,
        "upgraded_from_token": "",
        "status": "awaiting_intake",
        "subscription_pause": {"cancelled_now": True},
    }
    assert _one_off_eligible_for_upgrade_base_dropdown(row) is True


def test_no_infer_two_oneoffs_before_sub_without_name():
    from app import _infer_consumed_oneoff_tokens

    one_off1 = {
        "intake": {"business_name": "Harbour & Hearth"},
        "created_at": "2026-01-01T00:00:00+00:00",
        "status": "delivered",
        "token": "tok-a",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": None,
    }
    one_off2 = {
        "intake": {"business_name": "Other"},
        "created_at": "2026-01-15T00:00:00+00:00",
        "status": "delivered",
        "token": "tok-b",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": None,
    }
    sub_cancelled = {
        "intake": None,
        "created_at": "2026-03-01T00:00:00+00:00",
        "status": "delivered",
        "token": "tok-sub",
        "stripe_subscription_id": None,
        "subscription_cancelled_at": "2026-04-09T12:00:00+00:00",
        "upgraded_from_token": None,
    }
    out = _infer_consumed_oneoff_tokens([one_off1, one_off2, sub_cancelled], set())
    assert "tok-a" not in out
    assert "tok-b" not in out


def test_oneoff_not_blocked_when_only_cancelled_empty_upgrade_shell():
    """Cancelled upgrade row that never delivered must not hide the delivered base one-off from account lists."""
    from app import _oneoff_base_blocked_by_living_upgrade

    tok = "tok-kk-oneoff"
    orders = [
        {"token": tok, "status": "delivered", "delivered_at": "2026-01-01", "stripe_subscription_id": None},
        {
            "token": "tok-bad-sub",
            "status": "awaiting_intake",
            "stripe_subscription_id": None,
            "subscription_cancelled_at": "2026-04-01T00:00:00Z",
            "upgraded_from_token": tok,
        },
    ]
    assert _oneoff_base_blocked_by_living_upgrade(orders, tok) is False


def test_oneoff_blocked_when_active_subscription_references_token():
    from app import _oneoff_base_blocked_by_living_upgrade

    tok = "tok-kk-oneoff"
    orders = [
        {"token": tok, "status": "delivered", "stripe_subscription_id": None},
        {
            "token": "tok-sub",
            "status": "awaiting_intake",
            "stripe_subscription_id": "sub_live123",
            "subscription_cancelled_at": None,
            "upgraded_from_token": tok,
        },
    ]
    assert _oneoff_base_blocked_by_living_upgrade(orders, tok) is True


def test_oneoff_blocked_when_delivered_subscription_references_token():
    from app import _oneoff_base_blocked_by_living_upgrade

    tok = "tok-kk-oneoff"
    orders = [
        {"token": tok, "status": "delivered", "stripe_subscription_id": None},
        {
            "token": "tok-sub",
            "status": "delivered",
            "delivered_at": "2026-05-01",
            "stripe_subscription_id": None,
            "subscription_cancelled_at": "2026-06-01",
            "upgraded_from_token": tok,
        },
    ]
    assert _oneoff_base_blocked_by_living_upgrade(orders, tok) is True


if __name__ == "__main__":
    test_infer_when_sub_row_has_no_business_name_in_db()
    test_infer_ampersand_matches_and_in_business_name()
    test_infer_when_sub_missing_upgraded_from_token()
    test_no_infer_when_upgraded_from_already_in_db()
    test_no_infer_when_two_former_subs_same_business()
    test_no_infer_when_second_oneoff_between()
    test_no_infer_two_oneoffs_before_sub_without_name()
    test_one_off_eligible_former_sub_even_if_awaiting_intake()
    test_oneoff_not_blocked_when_only_cancelled_empty_upgrade_shell()
    test_oneoff_blocked_when_active_subscription_references_token()
    test_oneoff_blocked_when_delivered_subscription_references_token()
    print("OK")
