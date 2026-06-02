"""
Webhook handlers for third-party integrations.
Allows external services to send leads to the system.
"""
import re
import time
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify, current_app
from config import Config
webhook_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')

# --- Stripe (30 Days Captions) ---
CAPTIONS_AMOUNT_PENCE = 9700  # £97

# Dedupe ops email when Stripe retries checkout.session.completed (same session).
_CHECKOUT_MISSING_ORDER_ALERT_AT: Dict[str, float] = {}
_CHECKOUT_MISSING_ORDER_ALERT_TTL_SEC = 300.0


def _sanitize_base_url(raw: str) -> str:
    """Remove non-printable ASCII (e.g. newline from env) so URLs are valid."""
    if not raw or not isinstance(raw, str):
        return ""
    # Strip and remove control chars so SendGrid/URL validators don't raise
    s = re.sub(r"[\x00-\x1f\x7f]", "", raw.strip())
    return s.rstrip("/").strip()


def _sanitize_for_email(text: str) -> str:
    """Remove control chars (except newline) so SendGrid/APIs don't raise 'Invalid non-printable ASCII'."""
    if not text or not isinstance(text, str):
        return ""
    # Keep \n (0x0a) for line breaks; remove \r and other control chars
    return re.sub(r"[\x00-\x09\x0b-\x1f\x7f]", "", text)


def _invoice_subscription_id(invoice: Optional[dict]) -> str:
    """Stripe Invoice.subscription may be absent on newer APIs; subscription id can live under parent."""
    if not invoice or not isinstance(invoice, dict):
        return ""
    raw = invoice.get("subscription")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, dict):
        rid = (raw.get("id") or "").strip()
        if rid:
            return rid
    parent = invoice.get("parent")
    if isinstance(parent, dict) and parent.get("type") == "subscription_details":
        sd = parent.get("subscription_details") or {}
        if isinstance(sd, dict):
            sub = sd.get("subscription")
            if isinstance(sub, str) and sub.strip():
                return sub.strip()
            if isinstance(sub, dict):
                return (sub.get("id") or "").strip()
    return ""


def _format_paid_amount(amount_total, currency: str) -> str:
    """Format Stripe amount_total for customer-facing email copy."""
    if amount_total is None:
        return ""
    try:
        amt = int(amount_total)
    except (TypeError, ValueError):
        return ""
    curr = (currency or "gbp").strip().lower()
    if curr == "usd":
        return f"${amt / 100:.2f}"
    if curr == "eur":
        return f"€{amt / 100:.2f}"
    if curr == "gbp":
        return f"£{amt / 100:.2f}"
    return f"{amt / 100:.2f} {curr.upper()}"


def _coerce_platform_selection(raw: str, desired_count: int) -> str:
    """Normalize selected platforms and align count to subscription plan size."""
    desired = max(1, min(4, int(desired_count or 1)))
    defaults = ["Instagram & Facebook", "LinkedIn", "TikTok", "Pinterest"]
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    normalized = []
    seen = set()
    for p in parts:
        if p in ("Instagram", "Facebook"):
            p = "Instagram & Facebook"
        if p in defaults and p not in seen:
            seen.add(p)
            normalized.append(p)
    if not normalized:
        normalized = ["Instagram & Facebook"]
    for p in defaults:
        if len(normalized) >= desired:
            break
        if p not in normalized:
            normalized.append(p)
    return ", ".join(normalized[:desired])


def _should_send_plan_change_email(
    prev_attrs: dict,
    old_platforms: int,
    old_stories: bool,
    new_platforms: int,
    new_stories: bool,
) -> bool:
    """
    Guard plan-change confirmations to true plan changes only.
    Prevents false positives from unrelated subscription.updated events.
    """
    # Only send when the effective plan actually changed.
    # This avoids duplicate "plan updated" emails when the app endpoint already
    # synced the order and Stripe later emits subscription.updated with items in previous_attributes.
    return (old_platforms != new_platforms) or (old_stories != new_stories)


def _plan_change_dedupe_key(sub_id: str, email: str, new_platforms: int, new_stories: bool) -> str:
    """Stable key for plan-change confirmation dedupe (DB RPC + billing API)."""
    return f"{(sub_id or '').strip().lower()}|{(email or '').strip().lower()}|{int(new_platforms)}|{1 if new_stories else 0}"


def _checkout_session_metadata(session) -> dict:
    """Stripe checkout.session metadata from webhook JSON or SDK object (must not assume plain dict)."""
    if not isinstance(session, dict):
        return {}
    m = session.get("metadata")
    if isinstance(m, dict):
        return m
    if m is not None:
        try:
            if hasattr(m, "to_dict"):
                return m.to_dict()
            return dict(m)
        except Exception:
            pass
    return {}


def _checkout_session_customer_details(session) -> Dict[str, Any]:
    """customer_details may be dict or StripeObject; email lives here for Checkout."""
    if not isinstance(session, dict):
        return {}
    d = session.get("customer_details")
    if isinstance(d, dict):
        return d
    if d is not None:
        try:
            if hasattr(d, "to_dict"):
                return d.to_dict()
            return dict(d)
        except Exception:
            pass
    return {}


def _checkout_session_stripe_customer_id(session: dict | None) -> str:
    """Stripe Checkout Session.customer: id string, or expanded dict/object with id."""
    if not isinstance(session, dict):
        return ""
    c = session.get("customer")
    if not c:
        return ""
    if isinstance(c, str):
        return c.strip()
    if isinstance(c, dict):
        return (c.get("id") or "").strip()
    cid = getattr(c, "id", None)
    return str(cid).strip() if cid else ""


def _line_item_price_id(item: Any) -> Optional[str]:
    """Line item price may be expanded dict, or a string price_ id."""
    if not isinstance(item, dict):
        return None
    p = item.get("price")
    if isinstance(p, str) and p.strip():
        return p.strip()
    if isinstance(p, dict):
        pid = (p.get("id") or "").strip()
        return pid or None
    return None


def _is_captions_subscription_payment(session) -> bool:
    """True if this checkout is for 30 Days Captions subscription (£79/month). Reuses same intake/delivery as one-off."""
    mode = (session.get("mode") or "") if isinstance(session, dict) else ""
    if mode != "subscription":
        return False
    meta = _checkout_session_metadata(session)
    if meta.get("product") == "captions_subscription":
        return True
    sub_price_ids = [
        (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", None) or "").strip(),
        (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD", None) or "").strip(),
        (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR", None) or "").strip(),
    ]
    sub_price_ids = [x for x in sub_price_ids if x]
    for item in (session.get("line_items") or {}).get("data") or []:
        pid = _line_item_price_id(item)
        if pid and pid in sub_price_ids:
            return True
    return False


def _is_captions_payment(session) -> bool:
    """True if this checkout is for 30 Days Captions (one-off, any currency)."""
    meta = _checkout_session_metadata(session)
    if meta.get("product") == "captions":
        return True
    amount_raw = session.get("amount_total")
    try:
        amount = int(amount_raw) if amount_raw is not None else 0
    except (TypeError, ValueError):
        amount = 0
    currency = (session.get("currency") or "gbp").strip().lower() if isinstance(session, dict) else "gbp"
    if currency == "gbp" and amount == CAPTIONS_AMOUNT_PENCE:
        return True
    # Match by price ID (GBP, USD, EUR)
    captions_price_ids = []
    for key in ("STRIPE_CAPTIONS_PRICE_ID", "STRIPE_CAPTIONS_PRICE_ID_USD", "STRIPE_CAPTIONS_PRICE_ID_EUR"):
        pid = (getattr(Config, key, None) or "").strip()
        if pid:
            captions_price_ids.append(pid)
    for item in (session.get("line_items") or {}).get("data") or []:
        pid = _line_item_price_id(item)
        if pid and pid in captions_price_ids:
            return True
    # Captions checkout always sets metadata.platforms; if product key was dropped from the payload, still match.
    if (session.get("mode") or "") == "payment" and meta.get("platforms") is not None and meta.get("product") in (None, "", "captions"):
        print("[Stripe webhook] _is_captions_payment: matched via metadata.platforms (product key missing or captions)")
        return True
    return False


def _get_customer_email_from_session(session):
    """Get customer email from Stripe Checkout Session.

    Prefer customer_details.email. For Checkout with an existing Stripe Customer (`customer=cus_...`),
    Stripe often omits email from customer_details; use the Customer object's email in that case.
    """
    # #4 Fix: Email is usually in customer_details.email, NOT top-level customer_email (often null for Checkout)
    details = _checkout_session_customer_details(session) if isinstance(session, dict) else None
    if details:
        email = details.get("email") or details.get("customer_email")
        if email and isinstance(email, str):
            return email.strip()
    if hasattr(session, "get"):
        details = session.get("customer_details") if isinstance(session, dict) else None
    else:
        details = None
    if details is not None and not isinstance(details, dict):
        email = None
        if hasattr(details, "get"):
            email = details.get("email") or details.get("customer_email")
        else:
            email = getattr(details, "email", None) or getattr(details, "customer_email", None)
        if email and isinstance(email, str):
            return email.strip()
    # Top-level fallback (older payloads)
    email = session.get("customer_email") if hasattr(session, "get") else getattr(session, "customer_email", None)
    if email and isinstance(email, str):
        return email.strip()
    # Existing-customer checkout: email may only exist on the Customer object
    cust_raw = session.get("customer") if isinstance(session, dict) else None
    if cust_raw is not None:
        if isinstance(cust_raw, dict):
            em = cust_raw.get("email")
            if em and isinstance(em, str) and em.strip():
                return em.strip()
        elif isinstance(cust_raw, str) and cust_raw.startswith("cus_"):
            try:
                import stripe

                if Config.STRIPE_SECRET_KEY:
                    stripe.api_key = Config.STRIPE_SECRET_KEY
                    cobj = stripe.Customer.retrieve(cust_raw)
                    em = getattr(cobj, "email", None)
                    if em is None and isinstance(cobj, dict):
                        em = cobj.get("email")
                    if em and isinstance(em, str) and em.strip():
                        return em.strip()
            except Exception as e:
                print(f"[Stripe webhook] Customer.retrieve for checkout email failed: {e}")
    # If still missing, fetch the session from Stripe API (expand customer for same reason as above)
    try:
        import stripe
        sid = session.get("id") if hasattr(session, "get") else getattr(session, "id", None)
        if Config.STRIPE_SECRET_KEY and sid:
            stripe.api_key = Config.STRIPE_SECRET_KEY
            full = stripe.checkout.Session.retrieve(sid, expand=["customer_details", "customer"])
            details = full.get("customer_details") or {}
            if isinstance(details, dict):
                email = details.get("email") or details.get("customer_email")
            else:
                email = getattr(details, "email", None) or getattr(details, "customer_email", None)
            if email:
                return str(email).strip()
            email = full.get("customer_email")
            if email:
                return str(email).strip()
            fc = full.get("customer")
            if isinstance(fc, dict):
                em = fc.get("email")
                if em and isinstance(em, str) and em.strip():
                    return em.strip()
            elif isinstance(fc, str) and fc.startswith("cus_"):
                try:
                    cobj = stripe.Customer.retrieve(fc)
                    em = getattr(cobj, "email", None)
                    if em is None and isinstance(cobj, dict):
                        em = cobj.get("email")
                    if em and isinstance(em, str) and em.strip():
                        return em.strip()
                except Exception as e2:
                    print(f"[Stripe webhook] Customer.retrieve after Session.retrieve failed: {e2}")
    except Exception as e:
        print(f"[Stripe webhook] Could not retrieve session for email: {e}")
    return None


def _email_from_stripe_customer_field(cust: Any) -> str:
    """Return email from expanded Customer dict, expanded customer id string, or Customer object."""
    if cust is None:
        return ""
    if isinstance(cust, dict):
        em = cust.get("email")
        if em and isinstance(em, str) and em.strip():
            return em.strip()
        return ""
    cid = str(cust).strip()
    if not cid.startswith("cus_"):
        return ""
    try:
        import stripe

        if not (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip():
            return ""
        stripe.api_key = Config.STRIPE_SECRET_KEY.strip()
        cobj = stripe.Customer.retrieve(cid)
        em = getattr(cobj, "email", None)
        if em is None and isinstance(cobj, dict):
            em = cobj.get("email")
        if em and isinstance(em, str) and em.strip():
            return em.strip()
    except Exception as e:
        print(f"[Stripe webhook] Customer.retrieve ({cid[:12]}...) for checkout email failed: {e!r}")
    return ""


def _resolve_customer_email_after_checkout_session(
    subscription_id: Optional[str],
    customer_id: Optional[str],
) -> str:
    """
    Checkout Session payloads sometimes omit customer_details.email even after Session.retrieve.
    Without an email we skip create_order entirely — leaving an active Stripe subscription with no caption_orders row.
    Fall back to Subscription (expand customer) then Customer id.
    """
    if not (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip():
        return ""
    sid = (subscription_id or "").strip()
    cid = (customer_id or "").strip()
    if not sid and not cid:
        return ""
    try:
        import stripe

        stripe.api_key = Config.STRIPE_SECRET_KEY.strip()
        if sid:
            try:
                sub = stripe.Subscription.retrieve(sid, expand=["customer"])
                sub_d = sub.to_dict() if hasattr(sub, "to_dict") else dict(sub)
                em = _email_from_stripe_customer_field(sub_d.get("customer"))
                if em:
                    return em
            except Exception as e:
                print(f"[Stripe webhook] Subscription.retrieve for checkout email failed: {e!r}")
        if cid.startswith("cus_"):
            return _email_from_stripe_customer_field(cid)
    except Exception as e:
        print(f"[Stripe webhook] resolve customer email after checkout (non-fatal): {e!r}")
    return ""


def _stripe_expandable_id(value: Any) -> Optional[str]:
    """
    Checkout Session.retrieve(..., expand=['customer']) returns customer as a dict (or StripeObject),
    not a string. Normalise to cus_xxx / sub_xxx for DB columns and downstream .strip() callers.
    """
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s or None
    if isinstance(value, dict):
        rid = str(value.get("id") or "").strip()
        return rid or None
    rid = getattr(value, "id", None)
    if rid is not None:
        s = str(rid).strip()
        return s or None
    try:
        if hasattr(value, "to_dict"):
            d = value.to_dict()
            if isinstance(d, dict):
                rid = str(d.get("id") or "").strip()
                return rid or None
    except Exception:
        pass
    return None


def _normalize_checkout_session_ids_inplace(session: Any) -> Any:
    """
    Session.retrieve(..., expand=['customer']) embeds customer (and sometimes subscription) as objects.
    Downstream code expects cus_/sub_ strings; normalize in place when we can resolve an id.
    """
    if not isinstance(session, dict):
        return session
    cust = session.get("customer")
    cid = _stripe_expandable_id(cust)
    if cid:
        session["customer"] = cid
    sub = session.get("subscription")
    sid = _stripe_expandable_id(sub)
    if sid:
        session["subscription"] = sid
    return session


def _should_send_checkout_missing_order_ops_alert(session_id: str) -> bool:
    """At most one ops email per session per TTL (Stripe may retry the webhook many times)."""
    sid = (session_id or "").strip()
    if not sid:
        return True
    now = time.time()
    last = _CHECKOUT_MISSING_ORDER_ALERT_AT.get(sid, 0.0)
    if now - last < _CHECKOUT_MISSING_ORDER_ALERT_TTL_SEC:
        return False
    _CHECKOUT_MISSING_ORDER_ALERT_AT[sid] = now
    if len(_CHECKOUT_MISSING_ORDER_ALERT_AT) > 600:
        cutoff = now - _CHECKOUT_MISSING_ORDER_ALERT_TTL_SEC
        for k, t in list(_CHECKOUT_MISSING_ORDER_ALERT_AT.items()):
            if t < cutoff:
                del _CHECKOUT_MISSING_ORDER_ALERT_AT[k]
    return True


def _handle_captions_payment(session):
    """Create caption order and send intake-link email. Used for both one-off (£97) and subscription (£79/mo) captions.
    Idempotent: if we already have an order for this session, resend email and return."""
    from services.caption_order_service import CaptionOrderService
    from services.notifications import NotificationService

    if isinstance(session, dict):
        _normalize_checkout_session_ids_inplace(session)

    session_id = session.get("id") if isinstance(session, dict) else getattr(session, "id", None)
    cust_raw = session.get("customer") if isinstance(session, dict) else getattr(session, "customer", None)
    sub_raw = session.get("subscription") if isinstance(session, dict) else getattr(session, "subscription", None)
    stripe_customer_id = _stripe_expandable_id(cust_raw)
    stripe_subscription_id = _stripe_expandable_id(sub_raw)
    customer_email = _get_customer_email_from_session(session)
    if not customer_email:
        customer_email = _resolve_customer_email_after_checkout_session(
            stripe_subscription_id, stripe_customer_id
        )
    if not customer_email:
        print(
            "[Stripe webhook] No customer email in session (and no email on Subscription/Customer); "
            "caption_orders row NOT created — fix Stripe customer email or replay webhook after setting email."
        )
        return
    print(f"[Stripe webhook] Customer email from session: {customer_email}")

    # Reverse self-applied referral promo discount (Stripe allows entry; Lumo 22 enforces full price).
    payment_status = (session.get("payment_status") or "").strip().lower()
    if payment_status == "paid" and isinstance(session, dict):
        try:
            from services.stripe_referral_promotion import refund_self_referral_promotion_discount_if_needed

            refund_self_referral_promotion_discount_if_needed(session, payer_email=customer_email)
        except Exception as e:
            print(f"[Stripe webhook] self-referral discount refund wrapper: {e!r}")

    if stripe_customer_id:
        print(f"[Stripe webhook] Stripe customer: {stripe_customer_id[:20]}...")
    if stripe_subscription_id:
        print(f"[Stripe webhook] Stripe subscription: {stripe_subscription_id[:20]}...")

    meta = (session.get("metadata") or {}) if isinstance(session, dict) else getattr(session, "metadata", None) or {}
    if hasattr(meta, "get"):
        platforms_count = meta.get("platforms")
        selected_platforms = meta.get("selected_platforms")
        include_stories = meta.get("include_stories") in ("1", "true", "yes")
        reminder_opt_out = str(meta.get("reminder_opt_out") or "").strip().lower() in ("1", "true", "yes", "on")
    else:
        platforms_count = getattr(meta, "platforms", None)
        selected_platforms = getattr(meta, "selected_platforms", None)
        include_stories = getattr(meta, "include_stories", None) in ("1", "true", "yes")
        reminder_opt_out = str(getattr(meta, "reminder_opt_out", "") or "").strip().lower() in ("1", "true", "yes", "on")
    try:
        platforms_count = max(1, int(platforms_count)) if platforms_count is not None else 1
    except (TypeError, ValueError):
        platforms_count = 1
    selected_platforms = (selected_platforms or "").strip() or None

    currency = (session.get("currency") or "gbp") if isinstance(session, dict) else getattr(session, "currency", None) or "gbp"
    currency = str(currency).strip().lower()
    if currency not in ("gbp", "usd", "eur"):
        currency = "gbp"

    order_service = CaptionOrderService()
    # Idempotent: if Stripe retries or API created first, we may already have an order
    existing = order_service.get_by_stripe_session_id(session_id) if session_id else None
    if existing:
        print(
            f"[Stripe webhook] Order already exists for session {session_id[:20]}... "
            "(e.g. thank-you API created it first); will still send checkout email if not claimed yet"
        )
        order = existing
        updates = {}
        if stripe_customer_id and not existing.get("stripe_customer_id"):
            updates["stripe_customer_id"] = stripe_customer_id
        if stripe_subscription_id and not existing.get("stripe_subscription_id"):
            updates["stripe_subscription_id"] = stripe_subscription_id
        copy_from_meta = (
            (meta.get("copy_from") or "").strip()
            if isinstance(meta, dict)
            else str(getattr(meta, "copy_from", "") or "").strip()
        )
        copy_from_meta = copy_from_meta or None
        session_mode = (
            (session.get("mode") or "").strip().lower()
            if isinstance(session, dict)
            else str(getattr(session, "mode", "") or "").strip().lower()
        )
        is_sub_checkout = bool(stripe_subscription_id) or session_mode == "subscription"
        if (
            copy_from_meta
            and is_sub_checkout
            and stripe_subscription_id
            and not (existing.get("upgraded_from_token") or "").strip()
        ):
            updates["upgraded_from_token"] = copy_from_meta
        # Sample → paid one-off upgrade: persist the source sample token as upgraded_from_token so
        # the intake URL (added by _one_off_intake_url_with_copy_from) carries copy_from and the
        # intake form prefill same-email guard can read the source sample's intake.
        if (
            copy_from_meta
            and not is_sub_checkout
            and not (existing.get("upgraded_from_token") or "").strip()
        ):
            try:
                src_order = order_service.get_by_token(copy_from_meta)
            except Exception:
                src_order = None
            from services.caption_order_service import is_sample_pack_order

            if src_order and is_sample_pack_order(src_order):
                updates["upgraded_from_token"] = copy_from_meta
        if updates:
            order_service.update(existing["id"], updates)
            order = {**existing, **updates}
        if stripe_subscription_id and isinstance(meta, dict) and "reminder_opt_out" in meta:
            try:
                order_service.update(order["id"], {"reminder_opt_out": bool(reminder_opt_out)})
                order["reminder_opt_out"] = bool(reminder_opt_out)
            except Exception:
                pass
    else:
        try:
            copy_from = (meta.get("copy_from") or "").strip() if isinstance(meta, dict) else getattr(meta, "copy_from", None) or ""
            copy_from = str(copy_from).strip() if copy_from else None
            session_mode = (
                (session.get("mode") or "").strip().lower()
                if isinstance(session, dict)
                else str(getattr(session, "mode", "") or "").strip().lower()
            )
            is_sub_checkout = bool(stripe_subscription_id) or session_mode == "subscription"
            # Sample → paid one-off carries copy_from too. We persist upgraded_from_token whenever
            # copy_from points to a sample order (sub upgrade keeps its existing one-off path).
            upgraded_from_token_for_create: Optional[str] = None
            if copy_from:
                if is_sub_checkout:
                    upgraded_from_token_for_create = copy_from
                else:
                    try:
                        src_order = order_service.get_by_token(copy_from)
                    except Exception:
                        src_order = None
                    from services.caption_order_service import is_sample_pack_order

                    if src_order and is_sample_pack_order(src_order):
                        upgraded_from_token_for_create = copy_from
            order = order_service.create_order(
                customer_email=customer_email,
                stripe_session_id=session_id,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                platforms_count=platforms_count,
                selected_platforms=selected_platforms,
                include_stories=include_stories,
                currency=currency,
                upgraded_from_token=upgraded_from_token_for_create,
            )
        except Exception as e:
            print(f"[Stripe webhook] Failed to create order in Supabase: {e}")
            raise
        if stripe_subscription_id:
            try:
                order_service.update(order["id"], {"reminder_opt_out": bool(reminder_opt_out)})
                order["reminder_opt_out"] = bool(reminder_opt_out)
            except Exception as e:
                print(f"[Stripe webhook] Could not persist reminder_opt_out on create: {e}")
        print(f"[Stripe webhook] Order created id={order.get('id')} token=...{order['token'][-6:]}")
    # Merge checkout business name into intake before any emails (order confirmation + intake link).
    try:
        from api.captions_routes import seed_intake_business_from_stripe_metadata

        meta_for_seed = meta if isinstance(meta, dict) else {}
        if not meta_for_seed and meta is not None and hasattr(meta, "get"):
            meta_for_seed = {"business_name": meta.get("business_name"), "business_key": meta.get("business_key")}
        order = seed_intake_business_from_stripe_metadata(order_service, order, meta_for_seed)
    except Exception as e:
        print(f"[Stripe webhook] seed intake business_name (non-fatal): {e}")
    token = order["token"]
    base = _sanitize_base_url(Config.BASE_URL or "")
    if not base or not base.startswith("http"):
        base = "https://lumo-22-production.up.railway.app"
    safe_token = str(token).strip()
    copy_from = (meta.get("copy_from") or "").strip() if isinstance(meta, dict) else getattr(meta, "copy_from", None) or ""
    copy_from = str(copy_from).strip() if copy_from else ""
    # copy_from was already used above when creating order (as upgraded_from_token)
    intake_url = f"{base}/captions-intake?t={safe_token}"
    if copy_from:
        intake_url += f"&copy_from={copy_from}"

    # Send checkout email whenever we win the atomic claim — whether we created the order or thank-you API did first.
    oid = str(order.get("id") or "").strip()
    send_checkout_emails = not oid or order_service.try_claim_checkout_confirmation_email(oid)
    if oid and not send_checkout_emails:
        print(
            f"[Stripe webhook] Checkout confirmation email already sent for order {oid[:8]}...; "
            "skipping duplicate send"
        )
    if send_checkout_emails:
        notif = NotificationService()
        amount_total = session.get("amount_total") if isinstance(session, dict) else getattr(session, "amount_total", None)
        upgraded_from_oneoff = bool((order.get("upgraded_from_token") or copy_from or "").strip())
        is_trial_upgrade = upgraded_from_oneoff and (
            amount_total is None or (isinstance(amount_total, (int, float)) and int(amount_total) == 0)
        )
        if upgraded_from_oneoff:
            if is_trial_upgrade:
                first_charge_date_str = None
                if copy_from:
                    try:
                        from services.caption_order_service import CaptionOrderService
                        from datetime import datetime, timedelta, timezone

                        one_off = CaptionOrderService().get_by_token(copy_from)
                        if one_off:
                            raw = one_off.get("delivered_at") or one_off.get("updated_at") or one_off.get("created_at")
                            if raw:
                                dt = datetime.fromisoformat(raw.replace("Z", "+00:00")) if isinstance(raw, str) else raw
                                if getattr(dt, "tzinfo", None) is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                first_charge_date_str = (dt + timedelta(days=30)).strftime("%d %B %Y")
                    except Exception:
                        pass
                print(f"[Stripe webhook] Sending subscription upgrade confirmation (trial) to {customer_email}")
                ok = False
                try:
                    ok = notif.send_subscription_upgrade_confirmation_email(
                        customer_email,
                        intake_url,
                        first_charge_date_str,
                        order=order,
                    )
                except Exception as send_err:
                    print(f"[Stripe webhook] Upgrade confirmation send failed ({send_err}), retrying with fallback URL")
                    fallback_url = f"https://lumo-22-production.up.railway.app/captions-intake?t={safe_token}"
                    if copy_from:
                        fallback_url += f"&copy_from={copy_from}"
                    try:
                        ok = notif.send_subscription_upgrade_confirmation_email(
                            customer_email,
                            fallback_url,
                            first_charge_date_str,
                            order=order,
                        )
                    except Exception as fallback_err:
                        print(f"[Stripe webhook] Fallback also failed: {fallback_err}")
                        if oid:
                            order_service.release_checkout_confirmation_email_claim(oid)
                        raise
                if not ok:
                    print(f"[Stripe webhook] subscription upgrade confirmation email FAILED to send to {customer_email}")
                    if oid:
                        order_service.release_checkout_confirmation_email_claim(oid)
                else:
                    print(f"[Stripe webhook] subscription upgrade confirmation email sent to {customer_email}")
            else:
                print(f"[Stripe webhook] Sending subscription welcome (prefilled) email to {customer_email}")
                ok = False
                try:
                    amount_paid = _format_paid_amount(amount_total, (order.get("currency") or "gbp"))
                    ok = notif.send_subscription_welcome_prefilled_email(
                        customer_email,
                        intake_url,
                        order=order,
                        amount_paid=amount_paid,
                    )
                except Exception as send_err:
                    print(f"[Stripe webhook] Send failed ({send_err}), retrying with hardcoded fallback URL")
                    fallback_url = f"https://lumo-22-production.up.railway.app/captions-intake?t={safe_token}"
                    if copy_from:
                        fallback_url += f"&copy_from={copy_from}"
                    try:
                        amount_paid = _format_paid_amount(amount_total, (order.get("currency") or "gbp"))
                        ok = notif.send_subscription_welcome_prefilled_email(
                            customer_email,
                            fallback_url,
                            order=order,
                            amount_paid=amount_paid,
                        )
                    except Exception as fallback_err:
                        print(f"[Stripe webhook] Fallback send also failed: {fallback_err}")
                        if oid:
                            order_service.release_checkout_confirmation_email_claim(oid)
                        raise
                if not ok:
                    print(f"[Stripe webhook] subscription-welcome email FAILED to send to {customer_email}")
                    if oid:
                        order_service.release_checkout_confirmation_email_claim(oid)
                else:
                    print(f"[Stripe webhook] subscription-welcome email sent to {customer_email}")
        else:
            from api.captions_routes import _send_intake_email_for_order

            print(f"[Stripe webhook] Sending intake email to {customer_email}")
            ok = _send_intake_email_for_order(
                order, skip_checkout_confirmation_dedupe=True, checkout_session=session
            )
            if not ok:
                print(f"[Stripe webhook] intake-link email FAILED to send to {customer_email}")
            else:
                print(f"[Stripe webhook] intake-link email sent to {customer_email}")

    # Referrer reward: signup referral (referred_by) and/or friend's promotion code at Checkout. No credit if self-referral.
    try:
        from services.customer_auth_service import CustomerAuthService
        from services.stripe_referral_promotion import get_promotion_code_str_from_checkout_session

        auth_svc = CustomerAuthService()
        buyer = auth_svc.get_by_email(customer_email)
        buyer_email = (customer_email or "").strip().lower()
        sess_dict = session if isinstance(session, dict) else _stripe_nested_to_dict(session)
        promo_str = get_promotion_code_str_from_checkout_session(sess_dict)
        promo_owner = auth_svc.get_by_referral_code(promo_str) if promo_str else None
        if promo_owner and (promo_owner.get("email") or "").strip().lower() == buyer_email:
            print("[Stripe webhook] Referrer reward skipped: checkout email matches promotion code owner (self-referral).")
        else:
            referrer_id = None
            if buyer and buyer.get("referred_by_customer_id"):
                referrer_id = str(buyer["referred_by_customer_id"]).strip()
            if not referrer_id and promo_owner:
                referrer_id = str(promo_owner.get("id") or "").strip()
            if referrer_id and auth_svc.increment_referral_discount_credits(referrer_id):
                print(f"[Stripe webhook] Referrer reward: +1 credit for customer {referrer_id[:8]}... (friend paid)")
                try:
                    from services.notifications import NotificationService

                    referrer_row = auth_svc.get_by_id(referrer_id)
                    ref_email = (referrer_row.get("email") or "").strip() if referrer_row else ""
                    if ref_email:
                        base = _sanitize_base_url(Config.BASE_URL or "")
                        if not base or not base.startswith("http"):
                            base = "https://www.lumo22.com"
                        account_refer_url = f"{base}/account/refer"
                        credits_total = int((referrer_row or {}).get("referral_discount_credits") or 0)
                        notif_ref = NotificationService()
                        if notif_ref.send_referral_referrer_reward_email(
                            ref_email, account_refer_url, credits_total
                        ):
                            print(f"[Stripe webhook] Referrer reward email sent")
                        else:
                            print(f"[Stripe webhook] Referrer reward email failed (non-fatal)")
                except Exception as email_err:
                    print(f"[Stripe webhook] Referrer reward email (non-fatal): {email_err}")
    except Exception as e:
        print(f"[Stripe webhook] Referrer credit increment failed (non-fatal): {e}")


def _pack_sooner_webhook_ops_alert(
    reason: str,
    session: dict,
    order: Optional[dict],
    detail: str = "",
) -> None:
    """Email INTERNAL_ALERT_EMAIL when paid pack-sooner checkout did not start generation (non-fatal)."""
    try:
        from services.notifications import NotificationService

        sid = (session.get("id") or "").strip()
        oid = ""
        if order and order.get("id") is not None:
            oid = str(order.get("id") or "").strip()
        if not oid:
            meta = _checkout_session_metadata(session)
            oid = (meta.get("order_id") or "").strip()
        oemail = (order.get("customer_email") or "").strip() if order else ""
        NotificationService().send_caption_pack_sooner_webhook_blocked_alert(
            reason=reason,
            session_id=sid,
            order_id=oid,
            customer_email_order=oemail,
            detail=detail,
        )
    except Exception as e:
        print(f"[Stripe webhook] pack sooner ops alert (non-fatal): {e!r}")


def _handle_pack_sooner_checkout_completed(session: dict) -> None:
    """
    checkout.session.completed for fixed-price Get pack sooner (mode=payment).
    Resets subscription billing anchor (no mid-cycle adjustment line items), then triggers pack generation.
    """
    import stripe
    from services.caption_order_service import CaptionOrderService
    from api.captions_routes import (
        GET_PACK_SOONER_META_KEY,
        _run_generation_and_deliver,
        _subscription_pack_delivery_recent_duplicate,
        _subscription_pack_delivery_register,
    )

    session_id = (session.get("id") or "").strip()
    if not session_id:
        print("[Stripe webhook] pack sooner: missing session id")
        return
    meta = _checkout_session_metadata(session)
    if meta.get("product") != "captions_pack_sooner":
        return
    payment_status = (session.get("payment_status") or "").strip().lower()
    if payment_status != "paid":
        print(f"[Stripe webhook] pack sooner: payment_status={payment_status!r}; skipping")
        return
    order_id = (meta.get("order_id") or "").strip()
    sub_id = (meta.get("stripe_subscription_id") or "").strip()
    if not order_id or not sub_id:
        print("[Stripe webhook] pack sooner: missing order_id or stripe_subscription_id in metadata")
        _pack_sooner_webhook_ops_alert(
            "missing_order_or_subscription_in_metadata",
            session,
            None,
            detail=f"order_id={order_id!r} stripe_subscription_id={sub_id!r}",
        )
        return

    order_service = CaptionOrderService()
    order = order_service.get_by_id(order_id)
    if not order:
        print(f"[Stripe webhook] pack sooner: order {order_id} not found")
        _pack_sooner_webhook_ops_alert("order_not_found", session, None, detail=f"metadata order_id={order_id}")
        return
    if (order.get("stripe_subscription_id") or "").strip() != sub_id:
        print("[Stripe webhook] pack sooner: subscription id does not match order")
        _pack_sooner_webhook_ops_alert(
            "subscription_id_mismatch",
            session,
            order,
            detail=f"metadata sub={sub_id[:24]}… order sub={(order.get('stripe_subscription_id') or '')[:24]}…",
        )
        return
    order_email = (order.get("customer_email") or "").strip().lower()
    email_sess = (_get_customer_email_from_session(session) or "").strip().lower()
    cust_sess = _checkout_session_stripe_customer_id(session)
    cust_order = (order.get("stripe_customer_id") or "").strip()
    email_ok = bool(order_email and email_sess and order_email == email_sess)
    if not email_ok and cust_sess and cust_order and cust_sess == cust_order:
        # Checkout can show a prefilled email while webhook/API omit or differ on customer_details;
        # metadata + matching Stripe customer id is sufficient to bind this payment to the order.
        print(
            "[Stripe webhook] pack sooner: session vs order email mismatch or missing session email, "
            f"but Stripe customer matches order ({cust_sess[:12]}...); proceeding"
        )
        email_ok = True
    if not email_ok:
        print(
            "[Stripe webhook] pack sooner: email does not match order and Stripe customer id mismatch "
            f"(session_email={'set' if email_sess else 'empty'}, order_has_customer={bool(cust_order)})"
        )
        _pack_sooner_webhook_ops_alert(
            "checkout_email_or_customer_mismatch",
            session,
            order,
            detail=(
                f"order_email={order_email!r} session_email={email_sess!r} "
                f"stripe_customer_order={cust_order!r} stripe_customer_session={cust_sess!r}"
            ),
        )
        return
    if _subscription_pack_delivery_recent_duplicate(order_id):
        print(f"[Stripe webhook] pack sooner: delivery dedupe for order {order_id}; skipping")
        _pack_sooner_webhook_ops_alert(
            "delivery_dedupe_skip",
            session,
            order,
            detail="Another pack delivery for this order was registered within the dedupe window; "
            "generation was not started again. If the customer was charged and has no pack, check logs.",
        )
        return

    if not (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip():
        print("[Stripe webhook] pack sooner: STRIPE_SECRET_KEY missing")
        _pack_sooner_webhook_ops_alert("stripe_secret_missing", session, order, detail="Cannot call Stripe API.")
        return
    stripe.api_key = Config.STRIPE_SECRET_KEY.strip()
    try:
        from api.billing_routes import apply_pack_sooner_paid_plan_and_anchor

        ok_apply, err_apply = apply_pack_sooner_paid_plan_and_anchor(
            order,
            order_service,
            meta,
            get_pack_sooner_meta_key=GET_PACK_SOONER_META_KEY,
        )
        if not ok_apply:
            print(f"[Stripe webhook] pack sooner: apply plan+anchor failed: {err_apply!r}")
            _pack_sooner_webhook_ops_alert(
                "plan_anchor_apply_failed",
                session,
                order,
                detail=(err_apply or "")[:500],
            )
        order = order_service.get_by_id(order_id) or order
    except Exception as e:
        print(f"[Stripe webhook] pack sooner: Subscription.modify failed (non-fatal): {e!r}")

    pack_sooner_receipt = None
    try:
        from api.billing_routes import _subscription_monthly_price

        curr = (order.get("currency") or "gbp").strip().lower()
        if curr not in ("gbp", "usd", "eur"):
            curr = "gbp"
        platforms = max(1, int(order.get("platforms_count") or 1))
        include_stories = bool(order.get("include_stories"))
        sym, whole = _subscription_monthly_price(curr, platforms, include_stories)
        ongoing = f"{sym}{whole}/month"
        amount_paid = _format_paid_amount(
            session.get("amount_total"),
            (session.get("currency") or order.get("currency") or "gbp"),
        )
        pack_sooner_receipt = {
            "amount_paid_display": amount_paid,
            "ongoing_monthly_display": ongoing,
        }
    except Exception as e:
        print(f"[Stripe webhook] pack sooner: receipt context failed (non-fatal): {e!r}")

    import threading

    _subscription_pack_delivery_register(order_id)
    thread = threading.Thread(
        target=_run_generation_and_deliver,
        args=(order_id,),
        kwargs={"force_redeliver": True, "pack_sooner_receipt": pack_sooner_receipt},
    )
    thread.daemon = False
    thread.start()
    print(f"[Stripe webhook] pack sooner: generation started for order {order_id}")


def _is_subscription_cancelled_at_column_missing(exc: Exception) -> bool:
    """PostgREST when caption_orders.subscription_cancelled_at was never migrated."""
    s = str(exc)
    return "PGRST204" in s and "subscription_cancelled_at" in s


def _cancel_confirmation_already_sent(order: dict | None) -> bool:
    """True if we already emailed cancel confirmation for this caption_orders row."""
    if not order:
        return False
    v = order.get("cancel_confirmation_sent_at")
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    return True


def _stripe_nested_to_dict(obj):
    """Normalize Stripe API / webhook objects to dict for shared helpers."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    for name in ("to_dict_recursive", "to_dict"):
        fn = getattr(obj, name, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    try:
        return dict(obj)
    except Exception:
        return {}


def _send_captions_subscription_cancelled_confirmation(sub_id: str, sub_obj: dict | None) -> dict | None:
    """
    Send Lumo 22 cancellation confirmation email for a Captions Stripe subscription.

    Uses caption_orders when a row matches stripe_subscription_id. If none (stale DB,
    duplicate subs, webhook ordering), falls back to Stripe subscription + customer email.

    Returns the matched caption order dict when found (for reminder_opt_out updates), else None.
    """
    from services.caption_order_service import CaptionOrderService
    from services.notifications import NotificationService
    from api.billing_routes import _subscription_monthly_price, subscription_platforms_and_stories_from_stripe
    from api.captions_routes import _stripe_subscription_has_captions_base_price

    order_service = CaptionOrderService()
    order = order_service.get_by_stripe_subscription_id(sub_id)

    base = _sanitize_base_url(Config.BASE_URL or "https://www.lumo22.com")
    if not base or not base.startswith("http"):
        base = "https://www.lumo22.com"
    captions_url = base.rstrip("/") + "/captions"

    customer_email = None
    platforms, stories, currency = 1, False, "gbp"

    if order:
        customer_email = (order.get("customer_email") or "").strip()
        platforms = max(1, int(order.get("platforms_count", 1)))
        stories = bool(order.get("include_stories"))
        currency = (order.get("currency") or "gbp").strip().lower()
        if currency not in ("gbp", "usd", "eur"):
            currency = "gbp"
    else:
        import stripe

        if not Config.STRIPE_SECRET_KEY:
            print(
                f"[Stripe webhook] cancel confirmation: no caption_orders row for sub {sub_id[:20]}... "
                "and STRIPE_SECRET_KEY missing — cannot email customer"
            )
            return None
        stripe.api_key = Config.STRIPE_SECRET_KEY
        raw = sub_obj
        if not raw:
            try:
                raw = stripe.Subscription.retrieve(sub_id, expand=["customer"])
            except Exception as e:
                print(f"[Stripe webhook] cancel confirmation: Subscription.retrieve failed for {sub_id[:20]}...: {e}")
                return None
        sub_d = _stripe_nested_to_dict(raw)
        if not sub_d:
            print(f"[Stripe webhook] cancel confirmation: empty subscription payload for {sub_id[:20]}...")
            return None
        if not _stripe_subscription_has_captions_base_price(sub_d):
            print(f"[Stripe webhook] cancel confirmation: sub {sub_id[:20]}... is not Captions; skip email")
            return None
        platforms, stories = subscription_platforms_and_stories_from_stripe(sub_d)
        cur = sub_d.get("currency") or "gbp"
        currency = (cur if isinstance(cur, str) else "gbp").strip().lower()
        if currency not in ("gbp", "usd", "eur"):
            currency = "gbp"
        cust = sub_d.get("customer")
        cust_d = _stripe_nested_to_dict(cust) if cust is not None else {}
        customer_email = (cust_d.get("email") or "").strip()
        if not customer_email and isinstance(cust, str) and cust:
            try:
                c_raw = stripe.Customer.retrieve(cust)
                c_d = _stripe_nested_to_dict(c_raw)
                customer_email = (c_d.get("email") or "").strip()
            except Exception as e:
                print(f"[Stripe webhook] cancel confirmation: Customer.retrieve failed: {e}")
        if not customer_email:
            print(
                f"[Stripe webhook] cancel confirmation: no caption_orders row and no Stripe customer email "
                f"for sub {sub_id[:20]}..."
            )
            return None
        print(
            f"[Stripe webhook] cancel confirmation: no DB order for sub {sub_id[:20]}...; "
            f"sending via Stripe customer email fallback"
        )

    if not customer_email or "@" not in customer_email:
        print(f"[Stripe webhook] cancel confirmation: invalid email for sub {sub_id[:20]}...")
        return order

    claimed_cancel = False
    if order and order.get("id"):
        if not order_service.try_claim_cancel_confirmation_sent(str(order["id"])):
            return order
        claimed_cancel = True

    try:
        sym, amt = _subscription_monthly_price(currency, platforms, stories)
        plan_parts = [f"30 Days Captions, {platforms} platform{'s' if platforms != 1 else ''}"]
        if stories:
            plan_parts.append("Story Ideas")
        plan_summary = ", ".join(plan_parts)
        price_display = f"{sym}{amt}/month"
        notif = NotificationService()
        ok = notif.send_subscription_cancelled_email(
            customer_email,
            captions_url,
            plan_summary=plan_summary,
            price_display=price_display,
            business_name=((order.get("intake") or {}).get("business_name") if isinstance(order, dict) else None),
        )
        if ok:
            print(f"[Stripe webhook] cancel confirmation email sent → {customer_email} (sub …{sub_id[-8:]})")
        else:
            print(
                f"[Stripe webhook] cancel confirmation email NOT sent (send_email returned False) → {customer_email}"
            )
            if claimed_cancel:
                order_service.release_cancel_confirmation_claim(str(order["id"]))
    except Exception as e:
        print(f"[Stripe webhook] cancel confirmation email exception: {e}")
        if claimed_cancel:
            order_service.release_cancel_confirmation_claim(str(order["id"]))

    return order


@webhook_bp.route('/stripe', methods=['GET', 'POST'])
def stripe_webhook():
    """
    GET: Verify the webhook URL is reachable (open in browser).
    POST: Stripe webhook: checkout.session.completed for 30 Days Captions.
    """
    if request.method == 'GET':
        return jsonify({
            "message": "Stripe webhook endpoint. Stripe sends POST here.",
            "configured": bool(Config.STRIPE_WEBHOOK_SECRET),
        }), 200

    import stripe

    if not Config.STRIPE_WEBHOOK_SECRET:
        return jsonify({"error": "Stripe webhook not configured"}), 503

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, Config.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.SignatureVerificationError as e:
        return jsonify({"error": "Invalid signature"}), 400

    event_type = event.get("type") if hasattr(event, "get") else getattr(event, "type", None)
    print(f"[Stripe webhook] Webhook received: event.type={event_type}")

    try:
        if event_type == "invoice.paid":
            invoice = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not invoice or not isinstance(invoice, dict):
                print("[Stripe webhook] invoice.paid: missing or invalid invoice; skipping.")
                return jsonify({"received": True}), 200
            billing_reason = (invoice.get("billing_reason") or "").strip()
            sub_id = _invoice_subscription_id(invoice)
            if not sub_id:
                print("[Stripe webhook] invoice.paid: no subscription on invoice; skipping.")
                return jsonify({"received": True}), 200

            pack_sooner_update = False
            if billing_reason == "subscription_cycle":
                pass
            elif billing_reason == "subscription_update":
                stripe.api_key = Config.STRIPE_SECRET_KEY
                try:
                    sub_gate = stripe.Subscription.retrieve(sub_id)
                    md_gate = sub_gate.get("metadata") or {}
                    if (md_gate.get("lumo_get_pack_sooner") or "").strip() != "1":
                        print(
                            f"[Stripe webhook] invoice.paid: billing_reason=subscription_update "
                            f"but no lumo_get_pack_sooner flag; skipping."
                        )
                        return jsonify({"received": True}), 200
                    pack_sooner_update = True
                except Exception as e_gate:
                    print(f"[Stripe webhook] invoice.paid: subscription gate failed: {e_gate!r}; skipping.")
                    return jsonify({"received": True}), 200
            else:
                print(f"[Stripe webhook] invoice.paid: billing_reason={billing_reason}; skipping.")
                return jsonify({"received": True}), 200
            # Accept any captions subscription line (base + add-ons; some invoices may only list add-on prices)
            valid_price_ids = [
                p
                for p in [
                    (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", None) or "").strip(),
                    (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD", None) or "").strip(),
                    (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR", None) or "").strip(),
                    (getattr(Config, "STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID", None) or "").strip(),
                    (getattr(Config, "STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID", None) or "").strip(),
                ]
                if p
            ]
            if not valid_price_ids:
                return jsonify({"received": True}), 200
            is_captions = False
            lines_data = (invoice.get("lines") or {})
            if isinstance(lines_data, dict):
                lines_data = lines_data.get("data") or []
            if not isinstance(lines_data, list):
                lines_data = []
            for line in lines_data:
                price = line.get("price")
                if isinstance(price, dict):
                    pid = price.get("id")
                elif isinstance(price, str):
                    pid = price
                else:
                    pid = getattr(price, "id", None) if price else None
                if pid and pid in valid_price_ids:
                    is_captions = True
                    break
            if not is_captions:
                print("[Stripe webhook] invoice.paid: not captions subscription; skipping.")
                return jsonify({"received": True}), 200
            from services.caption_order_service import CaptionOrderService
            from api.captions_routes import (
                _run_generation_and_deliver,
                _subscription_pack_delivery_recent_duplicate,
                _subscription_pack_delivery_register,
            )
            import threading
            order_service = CaptionOrderService()
            order = order_service.get_by_stripe_subscription_id(sub_id)
            if not order:
                print(f"[Stripe webhook] invoice.paid: no order for subscription {sub_id[:20]}...; skipping.")
                return jsonify({"received": True}), 200
            order_id = order["id"]
            if not order.get("intake"):
                # Upgrader (trial just ended): copy intake from one-off so we can deliver
                copy_from = (order.get("upgraded_from_token") or "").strip()
                if copy_from:
                    one_off = order_service.get_by_token(copy_from)
                    if one_off and isinstance(one_off.get("intake"), dict):
                        order_service.save_intake(order_id, one_off["intake"])
                        order = order_service.get_by_id(order_id)
                if not order.get("intake"):
                    print(f"[Stripe webhook] invoice.paid: order {order_id} has no intake; skipping delivery.")
                    return jsonify({"received": True}), 200
            if pack_sooner_update:
                try:
                    stripe.api_key = Config.STRIPE_SECRET_KEY
                    stripe.Subscription.modify(sub_id, metadata={"lumo_get_pack_sooner": ""})
                except Exception as e_clr:
                    print(f"[Stripe webhook] invoice.paid: could not clear lumo_get_pack_sooner: {e_clr!r}")
                # Same Get pack sooner payment often emits checkout.session.completed AND invoice.paid.
                # Checkout registers a short dedupe window; without these guards invoice can start a second
                # force_redeliver run minutes later and send duplicate PDF emails (force_redeliver bypasses
                # "already delivered" for subscriptions).
                fresh = order_service.get_by_id(order_id) or order
                st = (fresh.get("status") or "").strip().lower()
                da_raw = (fresh.get("delivered_at") or "").strip()
                if st == "delivered" and da_raw:
                    try:
                        from datetime import datetime, timezone, timedelta

                        da = datetime.fromisoformat(da_raw.replace("Z", "+00:00"))
                        if da.tzinfo is None:
                            da = da.replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) - da < timedelta(hours=6):
                            print(
                                "[Stripe webhook] invoice.paid: pack sooner skip — order "
                                f"{order_id} already delivered at {da_raw} (within 6h; checkout path likely won)."
                            )
                            return jsonify({"received": True}), 200
                    except Exception:
                        pass
                if _subscription_pack_delivery_recent_duplicate(str(order_id)):
                    print(
                        "[Stripe webhook] invoice.paid: pack sooner skip — delivery dedupe window "
                        f"(checkout or parallel webhook already claimed this pack for order {order_id})."
                    )
                    return jsonify({"received": True}), 200
                _subscription_pack_delivery_register(str(order_id))
                print(
                    f"[Stripe webhook] invoice.paid: triggering generation for order {order_id} "
                    f"(get pack sooner / subscription_update)"
                )
            else:
                # subscription_cycle (normal renewals + first charge when Stripe uses this reason):
                # Intake submit often starts delivery first; invoice.paid can arrive minutes later with
                # force_redeliver=True and would send a duplicate PDF. Mirror pack-sooner guards.
                fresh_c = order_service.get_by_id(order_id) or order
                st_c = (fresh_c.get("status") or "").strip().lower()
                da_c = (fresh_c.get("delivered_at") or "").strip()
                if st_c == "delivered" and da_c:
                    try:
                        from datetime import datetime, timezone, timedelta

                        da = datetime.fromisoformat(da_c.replace("Z", "+00:00"))
                        if da.tzinfo is None:
                            da = da.replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) - da < timedelta(hours=6):
                            print(
                                "[Stripe webhook] invoice.paid: subscription_cycle skip — order "
                                f"{order_id} already delivered at {da_c} (within 6h; intake or checkout path likely won)."
                            )
                            return jsonify({"received": True}), 200
                    except Exception:
                        pass
                if _subscription_pack_delivery_recent_duplicate(str(order_id)):
                    print(
                        "[Stripe webhook] invoice.paid: subscription_cycle skip — delivery dedupe window "
                        f"(intake or parallel webhook already claimed this pack for order {order_id})."
                    )
                    return jsonify({"received": True}), 200
                _subscription_pack_delivery_register(str(order_id))
                print(
                    f"[Stripe webhook] invoice.paid: triggering generation for order {order_id} (subscription renewal)"
                )
            thread = threading.Thread(
                target=_run_generation_and_deliver,
                args=(order_id,),
                kwargs={"force_redeliver": True},
            )
            thread.daemon = False
            thread.start()
            return jsonify({"received": True}), 200

        if event_type == "customer.subscription.deleted":
            # Subscription ended in Stripe: send confirmation (if not already), then clear DB link so
            # account shows one-off-style Edit form + Resubscribe (see database_caption_orders_subscription_cancelled_at.sql).
            sub_obj = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not sub_obj or not isinstance(sub_obj, dict):
                return jsonify({"received": True}), 200
            sub_id = (sub_obj.get("id") or "").strip()
            if not sub_id:
                return jsonify({"received": True}), 200
            from datetime import datetime, timezone

            from services.caption_order_service import CaptionOrderService

            order_service = CaptionOrderService()
            existing = order_service.get_by_stripe_subscription_id(sub_id)
            if not existing:
                print(
                    f"[Stripe webhook] subscription.deleted: no caption_orders row for sub {sub_id[:20]}... "
                    "(already cleared or unknown)"
                )
                return jsonify({"received": True}), 200
            order_id = existing.get("id")
            if not order_id:
                return jsonify({"received": True}), 200

            if not _cancel_confirmation_already_sent(existing):
                _send_captions_subscription_cancelled_confirmation(sub_id, sub_obj)
            else:
                print(
                    f"[Stripe webhook] subscription.deleted: cancel email already sent for sub {sub_id[:20]}...; "
                    "skipping duplicate email"
                )

            now_iso = datetime.now(timezone.utc).isoformat()
            updates = {"stripe_subscription_id": None, "subscription_cancelled_at": now_iso}
            try:
                ok = order_service.update(str(order_id), updates)
            except Exception as e:
                if _is_subscription_cancelled_at_column_missing(e):
                    print(
                        "[Stripe webhook] subscription_cancelled_at column missing — run "
                        "database_caption_orders_subscription_cancelled_at.sql; clearing stripe_subscription_id only."
                    )
                    ok = order_service.update(str(order_id), {"stripe_subscription_id": None})
                else:
                    print(f"[Stripe webhook] subscription.deleted: DB update failed: {e!r}")
                    ok = False
            if ok:
                print(
                    f"[Stripe webhook] subscription.deleted: cleared stripe_subscription_id for order "
                    f"{str(order_id)[:8]}..."
                )
                try:
                    from app import invalidate_account_stripe_subscription_cache

                    invalidate_account_stripe_subscription_cache(sub_id)
                except Exception:
                    pass
            return jsonify({"received": True}), 200

        if event_type == "customer.subscription.updated":
            sub_obj = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not sub_obj or not isinstance(sub_obj, dict):
                return jsonify({"received": True}), 200
            sub_id = (sub_obj.get("id") or "").strip()
            if not sub_id:
                return jsonify({"received": True}), 200
            from services.caption_order_service import CaptionOrderService
            from services.notifications import NotificationService
            order_service = CaptionOrderService()
            order = order_service.get_by_stripe_subscription_id(sub_id)
            # Customer resumed: clear dedupe flag so a future cancel sends again
            prev_attrs = (event.get("data", {}) if isinstance(event, dict) else {}).get("previous_attributes") or {}
            if (
                order
                and order.get("id")
                and isinstance(prev_attrs, dict)
                and prev_attrs.get("cancel_at_period_end") is True
                and not sub_obj.get("cancel_at_period_end")
                and _cancel_confirmation_already_sent(order)
            ):
                try:
                    order_service.update(str(order["id"]), {"cancel_confirmation_sent_at": None})
                    print(
                        f"[Stripe webhook] subscription resumed (cancel_at_period_end cleared); "
                        f"reset cancel_confirmation_sent_at for order {str(order['id'])[:8]}..."
                    )
                except Exception as e:
                    print(f"[Stripe webhook] cancel_confirmation_sent_at clear failed: {e}")
            # Cancellation scheduled (cancel at period end) OR immediate cancel (status=canceled before delete).
            # Do not require a caption_orders row — email uses Stripe customer fallback when DB is missing.
            status = (sub_obj.get("status") or "").strip()
            cancel_scheduled = bool(sub_obj.get("cancel_at_period_end"))
            immediate_cancel = status == "canceled" and not cancel_scheduled
            if cancel_scheduled or immediate_cancel:
                if order and _cancel_confirmation_already_sent(order):
                    print(
                        f"[Stripe webhook] subscription.updated cancel: confirmation already sent for sub "
                        f"{sub_id[:20]}...; skipping duplicate webhook"
                    )
                    row = order
                    if row.get("id"):
                        try:
                            order_service.update(row["id"], {"reminder_opt_out": True})
                        except Exception as e:
                            print(f"[Stripe webhook] reminder_opt_out update on cancel failed: {e}")
                    return jsonify({"received": True}), 200
                order_for_reminder = _send_captions_subscription_cancelled_confirmation(sub_id, sub_obj)
                row = order_for_reminder or order
                if row and row.get("id"):
                    try:
                        order_service.update(row["id"], {"reminder_opt_out": True})
                    except Exception as e:
                        print(f"[Stripe webhook] reminder_opt_out update on cancel failed: {e}")
                elif cancel_scheduled:
                    print(
                        f"[Stripe webhook] cancel at period end: no caption_orders id for reminder_opt_out "
                        f"(sub {sub_id[:20]}...)"
                    )
                return jsonify({"received": True}), 200
            if not order:
                return jsonify({"received": True}), 200
            customer_email = (order.get("customer_email") or "").strip()
            base = (Config.BASE_URL or "https://www.lumo22.com").strip().rstrip("/")
            if not base.startswith("http"):
                base = "https://" + base
            # Plan change via Stripe billing portal: sync stored plan fields and send confirmation email.
            from api.billing_routes import (
                _subscription_monthly_price,
                merge_platform_list_with_stripe_count,
                subscription_platforms_and_stories_from_stripe,
            )
            if customer_email and "@" in customer_email:
                account_url = base + "/account"
                try:
                    currency = (order.get("currency") or "gbp").strip().lower()
                    old_platforms = max(1, int(order.get("platforms_count", 1)))
                    old_stories = bool(order.get("include_stories"))
                    new_platforms, new_stories = subscription_platforms_and_stories_from_stripe(sub_obj)
                    intake_existing = order.get("intake") if isinstance(order.get("intake"), dict) else {}
                    selected_source = (intake_existing.get("platform") or "").strip() or (order.get("selected_platforms") or "").strip()
                    selected_synced = merge_platform_list_with_stripe_count(selected_source, new_platforms)
                    updated_intake = dict(intake_existing or {})
                    updated_intake["platform"] = selected_synced
                    updated_intake["include_stories"] = new_stories
                    order_service.update(
                        order["id"],
                        {
                            "platforms_count": new_platforms,
                            "include_stories": new_stories,
                            "selected_platforms": selected_synced,
                            "intake": updated_intake,
                        },
                    )
                    if not _should_send_plan_change_email(
                        prev_attrs if isinstance(prev_attrs, dict) else {},
                        old_platforms,
                        old_stories,
                        new_platforms,
                        new_stories,
                    ):
                        print(
                            f"[Stripe webhook] subscription.updated: no plan delta for {sub_id[:20]}...; "
                            "skipping plan-change email"
                        )
                        return jsonify({"received": True}), 200
                    change_bits = []
                    if new_platforms != old_platforms:
                        change_bits.append(f"your subscription now includes {new_platforms} platform{'s' if new_platforms != 1 else ''} instead of {old_platforms}")
                    if (selected_synced or "").strip():
                        change_bits.append(f"your platforms are now: {(selected_synced or '').strip()}")
                    if new_stories and not old_stories:
                        change_bits.append("30 Days Story Ideas has been added to your subscription")
                    elif old_stories and not new_stories:
                        change_bits.append("Story Ideas has been removed from your subscription")
                    if not change_bits:
                        change_text = "your plan has been updated."
                    else:
                        change_text = "; ".join(change_bits) + "."
                    change_summary = f"What changed: {change_text}"
                    when_effective = "Changes apply to your next pack. Packs already delivered will not change."
                    old_sym, old_amt = _subscription_monthly_price(currency, old_platforms, old_stories)
                    new_sym, new_amt = _subscription_monthly_price(currency, new_platforms, new_stories)
                    notif = NotificationService()
                    dedupe_key = _plan_change_dedupe_key(sub_id, customer_email, new_platforms, new_stories)
                    oid = str(order.get("id") or "").strip()
                    claim = (
                        order_service.try_claim_plan_change_confirmation_sent(oid, dedupe_key)
                        if oid
                        else None
                    )
                    if claim is False:
                        print(
                            f"[Stripe webhook] subscription.updated: plan-change email deduped (DB) for "
                            f"{sub_id[:20]}... ({new_platforms} platforms, stories={1 if new_stories else 0})"
                        )
                        return jsonify({"received": True}), 200
                    if claim is None and oid:
                        print(
                            f"[Stripe webhook] subscription.updated: plan-change dedupe RPC unavailable; "
                            f"sending anyway for order {oid[:8]}..."
                        )
                    try:
                        ok = notif.send_plan_change_confirmation_email(
                            customer_email,
                            change_summary=change_summary,
                            when_effective=when_effective,
                            account_url=account_url,
                            new_price_display=f"{new_sym}{new_amt}",
                            old_price_display=f"{old_sym}{old_amt}",
                            business_name=((order.get("intake") or {}).get("business_name") if isinstance(order, dict) else None),
                        )
                        if not ok and claim is True and oid:
                            order_service.release_plan_change_confirmation_claim(oid)
                        if ok:
                            print(f"[Stripe webhook] Plan change confirmation sent to {customer_email}")
                    except Exception as send_exc:
                        if claim is True and oid:
                            order_service.release_plan_change_confirmation_claim(oid)
                        raise send_exc
                except Exception as e:
                    print(f"[Stripe webhook] Plan change confirmation email failed: {e}")
            return jsonify({"received": True}), 200

        if event_type == "invoice.created":
            # Apply referrer 10% discount to referrer's next billing period(s). One credit per referred friend; one credit consumed per invoice.
            invoice = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not invoice or not isinstance(invoice, dict):
                return jsonify({"received": True}), 200
            sub_id = _invoice_subscription_id(invoice)
            if not sub_id:
                return jsonify({"received": True}), 200
            invoice_id = (invoice.get("id") or "").strip()
            if not invoice_id:
                return jsonify({"received": True}), 200
            from services.caption_order_service import CaptionOrderService
            from services.customer_auth_service import CustomerAuthService
            from services.referral_reward_service import ReferralRewardService
            order_service = CaptionOrderService()
            order = order_service.get_by_stripe_subscription_id(sub_id)
            if not order:
                return jsonify({"received": True}), 200
            customer_email = (order.get("customer_email") or "").strip()
            if not customer_email:
                return jsonify({"received": True}), 200
            auth_svc = CustomerAuthService()
            customer = auth_svc.get_by_email(customer_email)
            if not customer:
                return jsonify({"received": True}), 200
            credits = int(customer.get("referral_discount_credits") or 0)
            if credits <= 0:
                return jsonify({"received": True}), 200
            reward_svc = ReferralRewardService()
            if reward_svc.has_redeemed_for_invoice(invoice_id):
                return jsonify({"received": True}), 200
            coupon_id = (getattr(Config, "STRIPE_REFERRAL_COUPON_ID", None) or "").strip()
            if not coupon_id:
                return jsonify({"received": True}), 200
            try:
                import stripe
                stripe.api_key = Config.STRIPE_SECRET_KEY
                stripe.Invoice.modify(
                    invoice_id,
                    discounts=[{"coupon": coupon_id}],
                )
            except Exception as e:
                print(f"[Stripe webhook] invoice.created: failed to apply referrer discount to {invoice_id[:20]}...: {e}")
                return jsonify({"received": True}), 200
            auth_svc.decrement_referral_discount_credits(str(customer["id"]))
            reward_svc.record_redemption(str(customer["id"]), invoice_id)
            print(f"[Stripe webhook] invoice.created: applied referrer 10% to invoice {invoice_id[:20]}... for {customer_email}")
            return jsonify({"received": True}), 200

        if event_type == "checkout.session.completed":
            session = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not session or not isinstance(session, dict):
                print("[Stripe webhook] checkout.session.completed: missing or invalid session object; skipping.")
                return jsonify({"received": True}), 200
            # Always retrieve the live session: webhook JSON often omits line_items / full metadata / customer_details.
            sid = (session.get("id") or "").strip()
            if sid and (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip():
                try:
                    import stripe
                    stripe.api_key = Config.STRIPE_SECRET_KEY.strip()
                    full = stripe.checkout.Session.retrieve(
                        sid,
                        expand=["line_items", "customer_details", "customer"],
                    )
                    session = full.to_dict() if hasattr(full, "to_dict") else dict(full)
                    session = _normalize_checkout_session_ids_inplace(session)
                except Exception as re_err:
                    print(f"[Stripe webhook] Session.retrieve failed; using webhook payload only: {re_err!r}")
            amount = session.get("amount_total")
            meta = _checkout_session_metadata(session)
            if meta.get("product") == "captions_pack_sooner":
                try:
                    _handle_pack_sooner_checkout_completed(session)
                except Exception as e:
                    import traceback

                    print(f"[Stripe webhook] pack sooner handler failed: {e}")
                    traceback.print_exc()
                    detail = (str(e) or repr(e))[:400]
                    detail = "".join(c for c in detail if ord(c) < 128)
                    return jsonify({"error": "Handler failed", "detail": detail or "Unknown error"}), 500
                return jsonify({"received": True}), 200
            is_captions = _is_captions_payment(session)
            is_captions_sub = _is_captions_subscription_payment(session)
            print(
                f"[Stripe webhook] checkout.session.completed amount_total={amount} metadata={meta} "
                f"is_captions={is_captions} is_captions_sub={is_captions_sub} session_id={sid[:20] if sid else '?'}"
            )
            if is_captions or is_captions_sub:
                try:
                    _handle_captions_payment(session)
                except Exception as e:
                    import traceback
                    print(f"[Stripe webhook] CAPTIONS HANDLER FAILED: {e}")
                    traceback.print_exc()
                    detail = (str(e) or repr(e))[:400]
                    detail = "".join(c for c in detail if ord(c) < 128)
                    return jsonify({"error": "Handler failed", "detail": detail or "Unknown error"}), 500
                # Any captions checkout must persist caption_orders for this session (all one-off + upgrade flows).
                from services.caption_order_service import CaptionOrderService
                from api.captions_routes import try_schedule_upgrade_get_pack_now_delivery
                from services.notifications import NotificationService

                sid_chk = (session.get("id") or "").strip() if isinstance(session, dict) else ""
                order_service_chk = CaptionOrderService()
                order_after = order_service_chk.get_by_stripe_session_id(sid_chk) if sid_chk else None
                if not order_after:
                    print(
                        "[Stripe webhook] CRITICAL: no caption_orders row after captions checkout handler — "
                        "returning 500 so Stripe retries; ops alert if not deduped."
                    )
                    if _should_send_checkout_missing_order_ops_alert(sid_chk):
                        try:
                            cust_alert = _stripe_expandable_id(
                                session.get("customer") if isinstance(session, dict) else None
                            )
                            sub_alert = _stripe_expandable_id(
                                session.get("subscription") if isinstance(session, dict) else None
                            )
                            em_alert = _get_customer_email_from_session(session) or ""
                            NotificationService().send_caption_checkout_webhook_missing_order_alert(
                                reason="no_row_after_handle_captions_payment",
                                session_id=sid_chk,
                                customer_email=em_alert,
                                stripe_customer_id=cust_alert or "",
                                stripe_subscription_id=sub_alert or "",
                                product_meta=str(meta.get("product") or ""),
                                is_subscription_checkout=bool(is_captions_sub),
                                copy_from=(meta.get("copy_from") or "").strip(),
                                detail=(
                                    "_handle_captions_payment returned without raising but no caption_orders row "
                                    "for this Checkout Session. Common causes: missing payer email on session until "
                                    "Customer is expanded, Supabase write failure, or idempotency mismatch. "
                                    "Check Railway logs and Stripe session; recovery: "
                                    "scripts/backfill_caption_order_from_stripe_subscription.py or "
                                    "scripts/backfill_caption_order_from_checkout_session.py."
                                ),
                            )
                        except Exception as alert_err:
                            print(f"[Stripe webhook] missing-order ops alert (non-fatal): {alert_err!r}")
                    else:
                        print("[Stripe webhook] missing-order ops alert suppressed (dedupe TTL for this session)")
                    return jsonify({"error": "caption order missing after captions checkout"}), 500
                # Upgrade + get pack now: same path as thank-you reconcile (dedupe + bind checks in helper).
                if is_captions_sub and (meta.get("get_pack_now") == "1") and (meta.get("copy_from") or "").strip():
                    try_schedule_upgrade_get_pack_now_delivery(
                        order_service_chk,
                        order_after,
                        session,
                        log_prefix="[Stripe webhook] get_pack_now",
                    )
            else:
                print("[Stripe webhook] Not a captions payment; no action.")

        return jsonify({"received": True}), 200
    except Exception as e:
        import traceback
        print(f"[Stripe webhook] UNEXPECTED ERROR: {e}")
        traceback.print_exc()
        detail = (str(e) or repr(e))[:400]
        detail = "".join(c for c in detail if ord(c) < 128)
        return jsonify({"error": "Internal server error", "detail": detail or "Unknown"}), 500

@webhook_bp.route('/typeform', methods=['POST'])
def typeform_webhook():
    """Typeform webhook. Lead capture discontinued; return 200 so integrations don't fail."""
    try:
        request.get_json(silent=True)
    except Exception:
        pass
    return jsonify({'ok': True}), 200

@webhook_bp.route('/zapier', methods=['POST'])
def zapier_webhook():
    """Zapier webhook. Lead capture discontinued; return 200 so integrations don't fail."""
    try:
        request.get_json(silent=True)
    except Exception:
        pass
    return jsonify({'ok': True}), 200

@webhook_bp.route('/sendgrid-inbound', methods=['POST'])
def sendgrid_inbound():
    """
    SendGrid Inbound Parse endpoint. DFD/Chat removed — return 200 so SendGrid doesn't retry.
    """
    return "", 200


@webhook_bp.route('/generic', methods=['POST'])
def generic_webhook():
    """Generic webhook. Lead capture discontinued; return 200 so integrations don't fail."""
    try:
        request.get_json(silent=True)
    except Exception:
        pass
    return jsonify({'ok': True}), 200
