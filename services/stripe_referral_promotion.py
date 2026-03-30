"""
Stripe Promotion Codes for refer-a-friend: one Promotion Code per customer, same underlying Coupon (STRIPE_REFERRAL_COUPON_ID).
Friends enter the code on Stripe Checkout; Lumo does not auto-apply discounts on Session.create.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from config import Config


def _promotion_code_fields(po: Any) -> tuple:
    """Return (code_upper, active) from Stripe PromotionCode object or dict."""
    if po is None:
        return "", False
    if isinstance(po, dict):
        return (str(po.get("code") or "").strip().upper(), bool(po.get("active")))
    code = str(getattr(po, "code", "") or "").strip().upper()
    return (code, bool(getattr(po, "active", False)))


def _coupon_id_from_promo_row(row: Any) -> str:
    """Stripe PromotionCode.coupon as id string."""
    if row is None:
        return ""
    c = row.get("coupon") if isinstance(row, dict) else getattr(row, "coupon", None)
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, dict):
        return str(c.get("id") or "").strip()
    return str(getattr(c, "id", "") or "").strip()


def _reconcile_promotion_id_from_stripe_list(
    stripe_mod: Any, *, code: str, coupon_id: str, _save_pc, log_prefix: str
) -> Optional[str]:
    """
    If Stripe already has an active promotion for this customer-facing code + coupon but DB has no id,
    persist that prom_xxx. Fixes cases where create succeeded in Stripe but DB save failed.
    """
    try:
        listed = stripe_mod.PromotionCode.list(code=code, limit=20)
        data = listed.get("data") if isinstance(listed, dict) else getattr(listed, "data", None) or []
        want = coupon_id.strip()
        for row in data:
            code_s, active = _promotion_code_fields(row)
            if not active or code_s != code:
                continue
            if _coupon_id_from_promo_row(row) != want:
                continue
            pid = row.get("id") if isinstance(row, dict) else getattr(row, "id", None)
            if pid:
                _save_pc(str(pid))
                return str(pid)
    except Exception as ex:
        print(f"{log_prefix} reconcile list failed: {ex!r}")
    return None


def ensure_stripe_promotion_code_for_customer(customer: Dict[str, Any]) -> Optional[str]:
    """
    Idempotently create a Stripe Promotion Code for this customer's referral_code.
    Persists customers.stripe_referral_promotion_code_id on success.
    Returns Stripe id (prom_xxx) or None if skipped / misconfigured / Stripe error.
    """
    coupon_id = (getattr(Config, "STRIPE_REFERRAL_COUPON_ID", None) or "").strip()
    secret = (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip()
    if not coupon_id or not secret:
        return None
    code = (customer.get("referral_code") or "").strip().upper()
    if len(code) < 4:
        return None
    cid = str(customer.get("id") or "").strip()
    if not cid:
        return None

    import stripe
    from services.customer_auth_service import CustomerAuthService

    stripe.api_key = secret
    auth = CustomerAuthService()

    def _save_pc(prom_id: str) -> None:
        if not auth.set_stripe_referral_promotion_code_id(cid, prom_id):
            print(f"[stripe_referral_promotion] persist promotion id failed for customer {cid[:8]}…")

    existing = (customer.get("stripe_referral_promotion_code_id") or "").strip()
    if existing:
        try:
            po = stripe.PromotionCode.retrieve(existing)
            code_stripe, active = _promotion_code_fields(po)
            if active and code_stripe == code:
                return existing
            print(
                f"[stripe_referral_promotion] stored prom {existing[:12]}… mismatch or inactive "
                f"(stripe_code={code_stripe!r} active={active}); clearing and recreating"
            )
        except Exception as e:
            print(f"[stripe_referral_promotion] stored prom id invalid, will recreate: {e!r}")
        auth.clear_stripe_referral_promotion_code_id(cid)

    linked = _reconcile_promotion_id_from_stripe_list(
        stripe,
        code=code,
        coupon_id=coupon_id,
        _save_pc=_save_pc,
        log_prefix="[stripe_referral_promotion]",
    )
    if linked:
        return linked

    try:
        pc = stripe.PromotionCode.create(coupon=coupon_id, code=code, active=True)
        pid = pc.get("id") if isinstance(pc, dict) else getattr(pc, "id", None)
        if pid:
            _save_pc(str(pid))
        return str(pid) if pid else None
    except Exception as e:
        err = str(e).lower()
        if "already been taken" in err or "already exists" in err or "duplicate" in err:
            try:
                listed = stripe.PromotionCode.list(code=code, limit=1)
                data = listed.get("data") if isinstance(listed, dict) else getattr(listed, "data", None)
                if data and len(data) > 0:
                    row = data[0]
                    pid = row.get("id") if isinstance(row, dict) else getattr(row, "id", None)
                    if pid:
                        _save_pc(str(pid))
                    return str(pid) if pid else None
            except Exception as ex2:
                print(f"[stripe_referral_promotion] list duplicate failed: {ex2!r}")
        print(f"[stripe_referral_promotion] create failed for {code[:4]}…: {e!r}")
        return None


def get_promotion_code_str_from_checkout_session(session_obj: Dict[str, Any]) -> Optional[str]:
    """
    Return the human referral code (e.g. AB12CD34) applied on Checkout, if any.
    Uses expanded Session when discounts reference a promotion_code.
    """
    import stripe

    session_id = (session_obj.get("id") or "").strip() if isinstance(session_obj, dict) else None
    if not session_id or not (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip():
        return None
    stripe.api_key = Config.STRIPE_SECRET_KEY
    try:
        sess = stripe.checkout.Session.retrieve(
            session_id,
            expand=["discounts.promotion_code"],
        )
    except Exception as e:
        print(f"[stripe_referral_promotion] retrieve session for promo: {e!r}")
        return None

    discounts = sess.get("discounts") if isinstance(sess, dict) else None
    if not discounts:
        return None
    for d in discounts:
        if not isinstance(d, dict):
            continue
        promo = d.get("promotion_code")
        if isinstance(promo, str):
            try:
                po = stripe.PromotionCode.retrieve(promo)
                code = (po.get("code") if isinstance(po, dict) else getattr(po, "code", None)) or ""
            except Exception:
                continue
        elif isinstance(promo, dict):
            code = (promo.get("code") or "").strip()
        else:
            code = getattr(promo, "code", None) or ""
        code = (code or "").strip().upper()
        if len(code) >= 4:
            return code
    return None
