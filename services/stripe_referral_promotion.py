"""
Stripe Promotion Codes for refer-a-friend: one Promotion Code per customer, same underlying Coupon (STRIPE_REFERRAL_COUPON_ID).
Friends enter the code on Stripe Checkout; Lumo does not auto-apply discounts on Session.create.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from config import Config

# Stripe PromotionCode metadata: documents referrer in Dashboard; self-use is blocked via refund webhook.
STRIPE_REFERRAL_PC_META_REFERRER_ID = "lumo_referrer_customer_id"


def _ensure_promotion_code_referrer_metadata(
    stripe_mod: Any, prom_id: str, referrer_customer_id: str, log_prefix: str
) -> None:
    """Set lumo_referrer_customer_id on the Stripe Promotion Code when missing or wrong."""
    if not prom_id or not referrer_customer_id:
        return
    try:
        po = stripe_mod.PromotionCode.retrieve(prom_id)
        meta = po.get("metadata") if isinstance(po, dict) else getattr(po, "metadata", None) or {}
        if not isinstance(meta, dict):
            meta = {}
        if str(meta.get(STRIPE_REFERRAL_PC_META_REFERRER_ID) or "").strip() == referrer_customer_id:
            return
        stripe_mod.PromotionCode.modify(
            prom_id, metadata={STRIPE_REFERRAL_PC_META_REFERRER_ID: referrer_customer_id}
        )
    except Exception as ex:
        print(f"{log_prefix} promotion metadata sync failed for {prom_id[:12]}…: {ex!r}")


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
    stripe_mod: Any,
    *,
    code: str,
    coupon_id: str,
    referrer_customer_id: str,
    _save_pc,
    log_prefix: str,
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
                _ensure_promotion_code_referrer_metadata(
                    stripe_mod, str(pid), referrer_customer_id, log_prefix
                )
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
                _ensure_promotion_code_referrer_metadata(
                    stripe, existing, cid, "[stripe_referral_promotion]"
                )
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
        referrer_customer_id=cid,
        _save_pc=_save_pc,
        log_prefix="[stripe_referral_promotion]",
    )
    if linked:
        return linked

    try:
        pc = stripe.PromotionCode.create(
            coupon=coupon_id,
            code=code,
            active=True,
            metadata={STRIPE_REFERRAL_PC_META_REFERRER_ID: cid},
        )
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
                        _ensure_promotion_code_referrer_metadata(
                            stripe, str(pid), cid, "[stripe_referral_promotion]"
                        )
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


def _payment_intent_id_from_checkout_session(session: Dict[str, Any]) -> str:
    pi = session.get("payment_intent")
    if isinstance(pi, dict):
        return str(pi.get("id") or "").strip()
    if isinstance(pi, str):
        return pi.strip()
    return ""


def _checkout_amount_discount_cents(session: Dict[str, Any]) -> int:
    """Smallest-currency-unit discount applied to the Checkout Session, if any."""
    td = session.get("total_details") or {}
    if not isinstance(td, dict):
        td = {}
    raw = td.get("amount_discount")
    try:
        n = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        n = 0
    if n > 0:
        return n
    try:
        sub = int(session.get("amount_subtotal") or 0)
        tot = int(session.get("amount_total") or 0)
    except (TypeError, ValueError):
        return 0
    if sub > tot:
        return sub - tot
    return 0


def refund_self_referral_promotion_discount_if_needed(
    session: Dict[str, Any], *, payer_email: str
) -> None:
    """
    Stripe Checkout cannot forbid entering your own referral promotion code. If the payer's email
    matches the Lumo customer who owns that code, refund only the promotion discount so they pay
    the undiscounted amount. No-op if no self-referral, no discount, or no payment_intent.

    Idempotent: uses Stripe idempotency key per Checkout Session id.
    """
    payer = (payer_email or "").strip().lower()
    if not payer or not isinstance(session, dict):
        return
    sid = (session.get("id") or "").strip()
    if not sid:
        return
    try:
        from services.customer_auth_service import CustomerAuthService

        promo_str = get_promotion_code_str_from_checkout_session(session)
        if not promo_str:
            return
        owner = CustomerAuthService().get_by_referral_code(promo_str)
        if not owner:
            return
        if (owner.get("email") or "").strip().lower() != payer:
            return
        discount = _checkout_amount_discount_cents(session)
        if discount <= 0:
            print(
                f"[stripe_referral_promotion] self-referral: code {promo_str[:4]}… owner matches payer "
                f"but amount_discount is 0; nothing to refund (session {sid[:16]}…)"
            )
            return
        pi = _payment_intent_id_from_checkout_session(session)
        if not pi.startswith("pi_"):
            print(
                f"[stripe_referral_promotion] self-referral: discount {discount} but no payment_intent "
                f"on session {sid[:16]}…; refund skipped"
            )
            return
        secret = (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip()
        if not secret:
            return
        import stripe

        stripe.api_key = secret
        stripe.Refund.create(
            payment_intent=pi,
            amount=discount,
            reason="requested_by_customer",
            idempotency_key=f"lumo-self-referral-discount-{sid}",
        )
        print(
            f"[stripe_referral_promotion] self-referral: refunded promotion discount "
            f"({discount} minor units) on payment_intent {pi[:20]}…"
        )
    except Exception as e:
        print(f"[stripe_referral_promotion] self-referral discount refund (non-fatal): {e!r}")
