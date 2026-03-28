"""
Webhook handlers for third-party integrations.
Allows external services to send leads to the system.
"""
import re
import time
from flask import Blueprint, request, jsonify, current_app
from config import Config
webhook_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')

# --- Stripe (30 Days Captions) ---
CAPTIONS_AMOUNT_PENCE = 9700  # £97
_plan_change_email_dedupe = {}
_PLAN_CHANGE_DEDUPE_TTL_SECONDS = 60 * 60  # 1 hour

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
    """Stable key for webhook plan-change confirmation dedupe."""
    return f"{(sub_id or '').strip().lower()}|{(email or '').strip().lower()}|{int(new_platforms)}|{1 if new_stories else 0}"


def _plan_change_email_recently_sent(dedupe_key: str, now_ts: float | None = None) -> bool:
    """True when this plan-change email key was sent recently in this process."""
    now = float(now_ts if now_ts is not None else time.time())
    # Opportunistic cleanup to keep dict bounded.
    stale_before = now - _PLAN_CHANGE_DEDUPE_TTL_SECONDS
    stale = [k for k, sent_at in _plan_change_email_dedupe.items() if sent_at < stale_before]
    for k in stale:
        _plan_change_email_dedupe.pop(k, None)
    sent_at = _plan_change_email_dedupe.get(dedupe_key)
    return bool(sent_at and (now - sent_at) < _PLAN_CHANGE_DEDUPE_TTL_SECONDS)


def _mark_plan_change_email_sent(dedupe_key: str, now_ts: float | None = None) -> None:
    """Record this plan-change key as sent for TTL-based dedupe."""
    _plan_change_email_dedupe[dedupe_key] = float(now_ts if now_ts is not None else time.time())


def _is_captions_subscription_payment(session) -> bool:
    """True if this checkout is for 30 Days Captions subscription (£79/month). Reuses same intake/delivery as one-off."""
    mode = (session.get("mode") or "") if isinstance(session, dict) else ""
    if mode != "subscription":
        return False
    meta = (session.get("metadata") or {}) if isinstance(session, dict) else {}
    if meta.get("product") == "captions_subscription":
        return True
    sub_price_ids = [
        (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", None) or "").strip(),
        (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD", None) or "").strip(),
        (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR", None) or "").strip(),
    ]
    sub_price_ids = [x for x in sub_price_ids if x]
    for item in (session.get("line_items") or {}).get("data") or []:
        pid = (item.get("price") or {}).get("id") if isinstance(item.get("price"), dict) else getattr(item.get("price"), "id", None)
        if pid and pid in sub_price_ids:
            return True
    return False


def _is_captions_payment(session) -> bool:
    """True if this checkout is for 30 Days Captions (one-off, any currency)."""
    meta = (session.get("metadata") or {}) if isinstance(session, dict) else {}
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
        pid = item.get("price", {}).get("id") if isinstance(item.get("price"), dict) else getattr(item.get("price"), "id", None)
        if pid and pid in captions_price_ids:
            return True
    return False


def _get_customer_email_from_session(session):
    """Get customer email from Stripe Checkout Session. Never use session.customer (it's null for Checkout)."""
    # #4 Fix: Email is in customer_details.email, NOT customer_email (which is null for Checkout)
    details = session.get("customer_details") if hasattr(session, "get") else None
    if details is not None:
        # Handle both dict and StripeObject (Stripe SDK may give object, not dict)
        email = None
        if isinstance(details, dict):
            email = details.get("email") or details.get("customer_email")
        elif hasattr(details, "get"):
            email = details.get("email") or details.get("customer_email")
        else:
            email = getattr(details, "email", None) or getattr(details, "customer_email", None)
        if email and isinstance(email, str):
            return email.strip()
    # Top-level fallback (older payloads)
    email = session.get("customer_email") if hasattr(session, "get") else getattr(session, "customer_email", None)
    if email and isinstance(email, str):
        return email.strip()
    # If still missing, fetch the session from Stripe API
    try:
        import stripe
        sid = session.get("id") if hasattr(session, "get") else getattr(session, "id", None)
        if Config.STRIPE_SECRET_KEY and sid:
            stripe.api_key = Config.STRIPE_SECRET_KEY
            full = stripe.checkout.Session.retrieve(sid, expand=["customer_details"])
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
    except Exception as e:
        print(f"[Stripe webhook] Could not retrieve session for email: {e}")
    return None


def _handle_captions_payment(session):
    """Create caption order and send intake-link email. Used for both one-off (£97) and subscription (£79/mo) captions.
    Idempotent: if we already have an order for this session, resend email and return."""
    from services.caption_order_service import CaptionOrderService
    from services.notifications import NotificationService

    session_id = session.get("id") if isinstance(session, dict) else getattr(session, "id", None)
    customer_email = _get_customer_email_from_session(session)
    if not customer_email:
        print("[Stripe webhook] No customer email in session; intake email not sent.")
        return
    print(f"[Stripe webhook] Customer email from session: {customer_email}")

    stripe_customer_id = (session.get("customer") or "").strip() or None
    stripe_subscription_id = (session.get("subscription") or "").strip() or None
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
    order_created_here = False
    if existing:
        print(f"[Stripe webhook] Order already exists for session {session_id[:20]}..., skipping emails (already sent)")
        order = existing
        if stripe_customer_id or stripe_subscription_id:
            updates = {}
            if stripe_customer_id and not existing.get("stripe_customer_id"):
                updates["stripe_customer_id"] = stripe_customer_id
            if stripe_subscription_id and not existing.get("stripe_subscription_id"):
                updates["stripe_subscription_id"] = stripe_subscription_id
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
            order = order_service.create_order(
                customer_email=customer_email,
                stripe_session_id=session_id,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                platforms_count=platforms_count,
                selected_platforms=selected_platforms,
                include_stories=include_stories,
                currency=currency,
                upgraded_from_token=copy_from if stripe_subscription_id else None,
            )
        except Exception as e:
            print(f"[Stripe webhook] Failed to create order in Supabase: {e}")
            raise
        order_created_here = True
        if stripe_subscription_id:
            try:
                order_service.update(order["id"], {"reminder_opt_out": bool(reminder_opt_out)})
                order["reminder_opt_out"] = bool(reminder_opt_out)
            except Exception as e:
                print(f"[Stripe webhook] Could not persist reminder_opt_out on create: {e}")
        print(f"[Stripe webhook] Order created id={order.get('id')} token=...{order['token'][-6:]}")
    # Merge checkout business name into intake before any emails (receipt / intake link).
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

    # Only send emails when we created the order; if existing, API or prior webhook already sent
    if order_created_here:
        notif = NotificationService()
        amount_total = session.get("amount_total") if isinstance(session, dict) else getattr(session, "amount_total", None)
        upgraded_from_oneoff = bool((order.get("upgraded_from_token") or copy_from or "").strip())
        is_trial_upgrade = upgraded_from_oneoff and (amount_total is None or (isinstance(amount_total, (int, float)) and int(amount_total) == 0))
        # For upgrades from one-off -> subscription we send a dedicated "prefilled form" email.
        # The standard receipt copy would incorrectly say "complete your short intake form" even though it was already filled/edited.
        if (not upgraded_from_oneoff) and (not is_trial_upgrade):
            try:
                notif.send_order_receipt_email(customer_email, order=order, session=session)
                time.sleep(2)  # Ensure confirmation is queued before intake so it arrives first
            except Exception as receipt_err:
                print(f"[Stripe webhook] Receipt email failed (non-fatal): {receipt_err}")
        if upgraded_from_oneoff:
            if is_trial_upgrade:
                # No charge today; send upgrade confirmation with charge date (no "payment received" receipt)
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
                        raise
                if not ok:
                    print(f"[Stripe webhook] subscription upgrade confirmation email FAILED to send to {customer_email}")
                else:
                    print(f"[Stripe webhook] subscription upgrade confirmation email sent to {customer_email}")
            else:
                # Charged at checkout (e.g. get pack now); send welcome prefilled
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
                        raise
                if not ok:
                    print(f"[Stripe webhook] subscription-welcome email FAILED to send to {customer_email}")
                else:
                    print(f"[Stripe webhook] subscription-welcome email sent to {customer_email}")
        else:
            print(f"[Stripe webhook] Sending intake email to {customer_email}")
            ok = False
            try:
                ok = notif.send_intake_link_email(customer_email, intake_url, order)
            except Exception as send_err:
                print(f"[Stripe webhook] Send failed ({send_err}), retrying with hardcoded fallback URL")
                fallback_url = f"https://lumo-22-production.up.railway.app/captions-intake?t={safe_token}"
                if copy_from:
                    fallback_url += f"&copy_from={copy_from}"
                try:
                    ok = notif.send_intake_link_email(customer_email, fallback_url, order)
                except Exception as fallback_err:
                    print(f"[Stripe webhook] Fallback send also failed: {fallback_err}")
                    raise
            if not ok:
                print(f"[Stripe webhook] intake-link email FAILED to send to {customer_email}")
            else:
                print(f"[Stripe webhook] intake-link email sent to {customer_email}")

    # Referrer reward: if the purchaser was referred (has account with referred_by_customer_id), give referrer one credit.
    try:
        from services.customer_auth_service import CustomerAuthService
        auth_svc = CustomerAuthService()
        buyer = auth_svc.get_by_email(customer_email)
        if buyer and buyer.get("referred_by_customer_id"):
            referrer_id = str(buyer["referred_by_customer_id"])
            if auth_svc.increment_referral_discount_credits(referrer_id):
                print(f"[Stripe webhook] Referrer reward: +1 credit for customer {referrer_id[:8]}... (referred friend paid)")
    except Exception as e:
        print(f"[Stripe webhook] Referrer credit increment failed (non-fatal): {e}")


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
    Send Lumo cancellation confirmation email for a Captions Stripe subscription.

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
            # Dedupe: subscription.updated (schedule/immediate) + subscription.deleted both fire — only one email
            if order and order.get("id"):
                from datetime import datetime

                ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                try:
                    order_service.update(str(order["id"]), {"cancel_confirmation_sent_at": ts})
                except Exception as ex:
                    print(f"[Stripe webhook] cancel_confirmation_sent_at update failed: {ex}")
        else:
            print(
                f"[Stripe webhook] cancel confirmation email NOT sent (send_email returned False) → {customer_email}"
            )
    except Exception as e:
        print(f"[Stripe webhook] cancel confirmation email exception: {e}")

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
            if billing_reason != "subscription_cycle":
                print(f"[Stripe webhook] invoice.paid: billing_reason={billing_reason}, not subscription_cycle; skipping.")
                return jsonify({"received": True}), 200
            sub_id = (invoice.get("subscription") or "").strip()
            if not sub_id:
                print("[Stripe webhook] invoice.paid: no subscription on invoice; skipping.")
                return jsonify({"received": True}), 200
            # Accept any captions subscription price (GBP, USD, EUR)
            valid_price_ids = [
                p for p in [
                    (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID", None) or "").strip(),
                    (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_USD", None) or "").strip(),
                    (getattr(Config, "STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID_EUR", None) or "").strip(),
                ] if p
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
            from api.captions_routes import _run_generation_and_deliver
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
            print(f"[Stripe webhook] invoice.paid: triggering generation for order {order_id} (subscription renewal)")
            thread = threading.Thread(target=_run_generation_and_deliver, args=(order_id,))
            thread.daemon = False
            thread.start()
            return jsonify({"received": True}), 200

        if event_type == "customer.subscription.deleted":
            # Subscription ended: send confirmation only if we did not already email on subscription.updated
            sub_obj = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not sub_obj or not isinstance(sub_obj, dict):
                return jsonify({"received": True}), 200
            sub_id = (sub_obj.get("id") or "").strip()
            if not sub_id:
                return jsonify({"received": True}), 200
            from services.caption_order_service import CaptionOrderService

            order_service = CaptionOrderService()
            existing = order_service.get_by_stripe_subscription_id(sub_id)
            if existing and _cancel_confirmation_already_sent(existing):
                print(
                    f"[Stripe webhook] subscription.deleted: cancel email already sent for sub {sub_id[:20]}...; "
                    "skipping duplicate"
                )
                return jsonify({"received": True}), 200
            _send_captions_subscription_cancelled_confirmation(sub_id, sub_obj)
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
            from api.billing_routes import _subscription_monthly_price, subscription_platforms_and_stories_from_stripe
            from services.caption_order_service import CaptionOrderService
            order_service = CaptionOrderService()
            if customer_email and "@" in customer_email:
                account_url = base + "/account"
                try:
                    currency = (order.get("currency") or "gbp").strip().lower()
                    old_platforms = max(1, int(order.get("platforms_count", 1)))
                    old_stories = bool(order.get("include_stories"))
                    new_platforms, new_stories = subscription_platforms_and_stories_from_stripe(sub_obj)
                    intake_existing = order.get("intake") if isinstance(order.get("intake"), dict) else {}
                    selected_source = (intake_existing.get("platform") or "").strip() or (order.get("selected_platforms") or "").strip()
                    selected_synced = _coerce_platform_selection(selected_source, new_platforms)
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
                    if _plan_change_email_recently_sent(dedupe_key):
                        print(
                            f"[Stripe webhook] subscription.updated: plan-change email deduped for {sub_id[:20]}... "
                            f"({new_platforms} platforms, stories={1 if new_stories else 0})"
                        )
                        return jsonify({"received": True}), 200
                    notif.send_plan_change_confirmation_email(
                        customer_email,
                        change_summary=change_summary,
                        when_effective=when_effective,
                        account_url=account_url,
                        new_price_display=f"{new_sym}{new_amt}",
                        old_price_display=f"{old_sym}{old_amt}",
                        business_name=((order.get("intake") or {}).get("business_name") if isinstance(order, dict) else None),
                    )
                    _mark_plan_change_email_sent(dedupe_key)
                    print(f"[Stripe webhook] Plan change confirmation sent to {customer_email}")
                except Exception as e:
                    print(f"[Stripe webhook] Plan change confirmation email failed: {e}")
            return jsonify({"received": True}), 200

        if event_type == "invoice.created":
            # Apply referrer 10% discount to referrer's next billing period(s). One credit per referred friend; one credit consumed per invoice.
            invoice = event.get("data", {}).get("object") if isinstance(event, dict) else None
            if not invoice or not isinstance(invoice, dict):
                return jsonify({"received": True}), 200
            sub_id = (invoice.get("subscription") or "").strip()
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
            amount = session.get("amount_total")
            meta = (session.get("metadata") or {}) if isinstance(session.get("metadata"), dict) else {}
            is_captions = _is_captions_payment(session)
            is_captions_sub = _is_captions_subscription_payment(session)
            print(f"[Stripe webhook] checkout.session.completed amount_total={amount} metadata={meta} is_captions={is_captions} is_captions_sub={is_captions_sub}")
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
                # Upgrade + get pack now: one charge (subscription). Copy intake from one-off and deliver immediately; next pack in 30 days.
                if is_captions_sub and (meta.get("get_pack_now") == "1") and (meta.get("copy_from") or "").strip():
                    try:
                        from services.caption_order_service import CaptionOrderService
                        from api.captions_routes import _run_generation_and_deliver
                        import threading
                        session_id = session.get("id") if isinstance(session, dict) else getattr(session, "id", None)
                        copy_from = (meta.get("copy_from") or "").strip()
                        order_service = CaptionOrderService()
                        order = order_service.get_by_stripe_session_id(session_id) if session_id else None
                        one_off = order_service.get_by_token(copy_from) if copy_from else None
                        if order and one_off:
                            intake = one_off.get("intake") if isinstance(one_off.get("intake"), dict) else None
                            if intake:
                                synced_intake = dict(intake)
                                selected = (order.get("selected_platforms") or "").strip()
                                if selected:
                                    synced_intake["platform"] = selected
                                synced_intake["include_stories"] = bool(order.get("include_stories"))
                                order_service.save_intake(order["id"], synced_intake)
                                thread = threading.Thread(target=_run_generation_and_deliver, args=(order["id"],))
                                thread.daemon = False
                                thread.start()
                                print(f"[Stripe webhook] get_pack_now: copied intake, delivery started for order {order['id']}")
                            else:
                                print(f"[Stripe webhook] get_pack_now: one-off order has no intake, skipping immediate delivery")
                        else:
                            print(f"[Stripe webhook] get_pack_now: order or one-off not found, skipping immediate delivery")
                    except Exception as e:
                        import traceback
                        print(f"[Stripe webhook] get_pack_now delivery failed (non-fatal): {e}")
                        traceback.print_exc()
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
