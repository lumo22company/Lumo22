"""
Caption order service: create and update 30 Days Captions orders in Supabase.
Used by Stripe webhook (create) and intake API (update + trigger generation).
"""
import base64
import json
import re
from typing import Dict, Any, Optional, List
from supabase import create_client, Client
from postgrest.types import CountMethod
from datetime import datetime, timezone, timedelta
import uuid
import secrets
from config import Config


def _is_checkout_claim_column_missing(exc: Exception) -> bool:
    """PostgREST when caption_orders.checkout_confirmation_email_sent_at was never migrated."""
    s = str(exc)
    return "PGRST204" in s and "checkout_confirmation_email_sent_at" in s


def _is_unique_stripe_session_violation(exc: Exception) -> bool:
    """True if insert failed because stripe_session_id already exists (PostgREST / Postgres)."""
    s = str(exc).lower()
    if "23505" in s or "duplicate key" in s or "unique constraint" in s or "already exists" in s:
        return True
    code = getattr(exc, "code", None)
    if code == "23505":
        return True
    return False


def _token() -> str:
    return secrets.token_urlsafe(16)


def coerce_json_list(val: Any) -> list:
    """Normalize JSONB list columns (PostgREST sometimes returns a JSON string)."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _stripe_customer_ids_for_login_email(email: str) -> list:
    """
    Stripe Customer.list(email=...) for the account email. Used when caption_orders has no row
    for this email (e.g. checkout used another address) but Stripe still has this email on the
    customer record, so we can load orders by stripe_customer_id.
    """
    if not email or "@" not in email:
        return []
    key = (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip()
    if not key:
        return []
    try:
        import stripe

        stripe.api_key = key
        em = (email or "").strip().lower()
        out: List[str] = []
        seen: set = set()

        def _add_customer_obj(c) -> None:
            cid = (getattr(c, "id", None) or (c.get("id") if isinstance(c, dict) else None) or "").strip()
            if cid and cid not in seen:
                seen.add(cid)
                out.append(cid)

        resp = stripe.Customer.list(email=em, limit=20)
        for c in resp.data or []:
            _add_customer_obj(c)
        if not out:
            try:
                safe = em.replace("\\", "\\\\").replace('"', '\\"')
                sresp = stripe.Customer.search(query=f'email:"{safe}"', limit=20)
                for c in getattr(sresp, "data", None) or []:
                    _add_customer_obj(c)
            except Exception:
                pass
        return out
    except Exception:
        return []


def _stripe_subscription_ids_for_customer_ids(customer_ids: List[str]) -> List[str]:
    """List active/past subscription ids for Stripe customer ids (links orders missing stripe_customer_id)."""
    if not customer_ids:
        return []
    key = (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip()
    if not key:
        return []
    out: List[str] = []
    seen: set = set()
    try:
        import stripe

        stripe.api_key = key
        for cus in customer_ids:
            cus = (cus or "").strip()
            if not cus:
                continue
            try:
                subs = stripe.Subscription.list(customer=cus, limit=100)
                for sub in subs.data or []:
                    sid = getattr(sub, "id", None)
                    if not sid and isinstance(sub, dict):
                        sid = sub.get("id")
                    sid = (sid or "").strip()
                    if sid and sid not in seen:
                        seen.add(sid)
                        out.append(sid)
            except Exception:
                pass
        return out
    except Exception:
        return []


def _sanitize_url(u: str) -> str:
    """Remove control chars so httpx/urlparse don't raise InvalidURL (e.g. newline in env)."""
    if not u or not isinstance(u, str):
        return (u or "").strip() or ""
    return re.sub(r"[\x00-\x1f\x7f]", "", (u or "").strip()).rstrip("/").strip()


def order_includes_stories_addon(order: Optional[Dict[str, Any]]) -> bool:
    """
    True when this pack includes Story Ideas for UI and downloads.
    Prefer caption_orders.include_stories; also respect intake.include_stories and stored stories PDF
    when the column was not synced (e.g. legacy rows or partial webhook updates).
    """
    if not order:
        return False
    if bool(order.get("include_stories")):
        return True
    if (order.get("stories_pdf_base64") or "").strip():
        return True
    intake = order.get("intake")
    if isinstance(intake, dict) and bool(intake.get("include_stories")):
        return True
    return False


def archive_entry_includes_stories(entry: Optional[Dict[str, Any]]) -> bool:
    """True if a delivery_archive row had Story Ideas (flag or stored PDF)."""
    if not entry or not isinstance(entry, dict):
        return False
    if bool(entry.get("include_stories")):
        return True
    if (entry.get("stories_pdf_base64") or "").strip():
        return True
    return False


def get_pack_download_payload(
    order: Optional[Dict[str, Any]], archive_index: Optional[int]
) -> Optional[Dict[str, Any]]:
    """
    Resolve captions/stories source for download. archive_index None = current row;
    0..n = delivery_archive[index] (subscription past packs).
    """
    if not order:
        return None
    if archive_index is None:
        dm = (order.get("delivered_at") or order.get("created_at") or "")[:10]
        return {
            "captions_md": order.get("captions_md") or "",
            "captions_pdf_base64": (order.get("captions_pdf_base64") or "").strip(),
            "stories_pdf_base64": (order.get("stories_pdf_base64") or "").strip(),
            "include_stories": order_includes_stories_addon(order),
            "date_str": dm,
        }
    arch = coerce_json_list(order.get("delivery_archive"))
    if archive_index < 0 or archive_index >= len(arch):
        return None
    a = arch[archive_index]
    if not isinstance(a, dict):
        return None
    da = (a.get("delivered_at") or "")[:10]
    return {
        "captions_md": a.get("captions_md") or "",
        "captions_pdf_base64": (a.get("captions_pdf_base64") or "").strip(),
        "stories_pdf_base64": (a.get("stories_pdf_base64") or "").strip(),
        "include_stories": archive_entry_includes_stories(a),
        "date_str": da,
    }


class CaptionOrderService:
    """CRUD for caption_orders table."""

    def __init__(self):
        key = (getattr(Config, "SUPABASE_SERVICE_ROLE_KEY", None) or Config.SUPABASE_KEY or "").strip()
        if not Config.SUPABASE_URL or not key:
            raise ValueError("Supabase configuration missing")
        url = _sanitize_url(Config.SUPABASE_URL)
        if not url:
            raise ValueError("Supabase configuration missing")
        # Service role bypasses RLS; anon key often cannot UPDATE caption_orders (claim column), so checkout emails never send.
        self.client: Client = create_client(url, key)
        self.table = "caption_orders"

    def create_order(
        self,
        customer_email: str,
        stripe_session_id: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        platforms_count: int = 1,
        selected_platforms: Optional[str] = None,
        include_stories: bool = False,
        currency: Optional[str] = None,
        upgraded_from_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create order after payment. Returns dict with id, token, customer_email, status.
        platforms_count: number of platforms paid for (1 = base, 2+ = base + add-ons).
        selected_platforms: comma-separated platforms chosen at checkout (e.g. Instagram, LinkedIn).
        include_stories: True when customer paid for 30 Days Story Ideas add-on at checkout.
        currency: payment currency (gbp, usd, eur). Used for subscribe_url so subscription checkout shows correct currency.
        upgraded_from_token: For subscription orders upgraded from one-off; first pack delivered 30 days after one-off."""
        token = _token()
        curr = (currency or "gbp").strip().lower()
        if curr not in ("gbp", "usd", "eur"):
            curr = "gbp"
        # Normalize email to lowercase so account dashboard (get_by_customer_email) finds the order
        customer_email_normalized = (customer_email or "").strip().lower()
        row = {
            "token": token,
            "customer_email": customer_email_normalized,
            "status": "awaiting_intake",
            "stripe_session_id": stripe_session_id,
            "stripe_customer_id": (stripe_customer_id or "").strip() or None,
            "stripe_subscription_id": (stripe_subscription_id or "").strip() or None,
            "platforms_count": max(1, int(platforms_count)),
            "selected_platforms": (selected_platforms or "").strip() or None,
            "include_stories": bool(include_stories),
            "currency": curr,
            "upgraded_from_token": (upgraded_from_token or "").strip() or None,
        }
        try:
            result = self.client.table(self.table).insert(row).execute()
        except Exception as e:
            sid = (stripe_session_id or "").strip()
            if sid and _is_unique_stripe_session_violation(e):
                existing = self.get_by_stripe_session_id(sid)
                if existing:
                    return existing
            raise
        if not result.data:
            raise RuntimeError("Failed to create caption order")
        self.remove_from_deleted_blocklist(customer_email_normalized)
        return result.data[0]

    def get_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get order by intake token."""
        result = self.client.table(self.table).select("*").eq("token", token).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def has_subscription_upgraded_from_oneoff_token(self, oneoff_token: str) -> bool:
        """True if a subscription caption_orders row lists this token as upgraded_from_token."""
        t = (oneoff_token or "").strip()
        if not t:
            return False
        try:
            result = (
                self.client.table(self.table)
                .select("stripe_subscription_id")
                .eq("upgraded_from_token", t)
                .limit(5)
                .execute()
            )
            for row in result.data or []:
                if (row.get("stripe_subscription_id") or "").strip():
                    return True
        except Exception:
            pass
        return False

    def get_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order by id."""
        result = self.client.table(self.table).select("*").eq("id", order_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def get_by_customer_email(self, email: str) -> list:
        """Get all caption orders for a customer email (case-insensitive so account always finds orders)."""
        if not email or "@" not in email:
            return []
        e = (email or "").strip()
        if not e:
            return []
        # Exact match first (normalized lowercase)
        result = self.client.table(self.table).select("*").eq("customer_email", e.lower()).order("created_at", desc=True).execute()
        data = result.data or []
        # If no match, try case-insensitive (e.g. order stored as "Skoverment@gmail.com")
        if not data:
            result = self.client.table(self.table).select("*").ilike("customer_email", e.lower()).order("created_at", desc=True).execute()
            data = result.data or []
            # Normalize stored email to lowercase so next time eq matches
            for o in data:
                oid = o.get("id")
                current = (o.get("customer_email") or "").strip()
                if oid and current and current != current.lower():
                    self.update(str(oid), {"customer_email": current.lower()})
        return data

    def get_by_customer_email_including_stripe_customer(self, email: str) -> list:
        """Get all caption orders for this customer: by email, and any orders with the same Stripe customer ID.
        Ensures the latest order shows even if they checked out with a different email (same Stripe customer)."""
        orders_by_email = self.get_by_customer_email(email)
        seen_ids = {o.get("id") for o in orders_by_email if o.get("id")}
        unique_sc_ids = []
        seen_sc = set()
        for o in orders_by_email:
            sc = (o.get("stripe_customer_id") or "").strip()
            if sc and sc not in seen_sc:
                seen_sc.add(sc)
                unique_sc_ids.append(sc)
        # Stripe may have this login email on file even when every caption_orders row used another email
        for sc in _stripe_customer_ids_for_login_email(email):
            if sc and sc not in seen_sc:
                seen_sc.add(sc)
                unique_sc_ids.append(sc)
        if unique_sc_ids:
            try:
                result = (
                    self.client.table(self.table)
                    .select("*")
                    .in_("stripe_customer_id", unique_sc_ids)
                    .order("created_at", desc=True)
                    .execute()
                )
                for row in result.data or []:
                    if row.get("id") and row["id"] not in seen_ids:
                        seen_ids.add(row["id"])
                        orders_by_email.append(row)
            except Exception:
                for sc_id in unique_sc_ids:
                    try:
                        result = (
                            self.client.table(self.table)
                            .select("*")
                            .eq("stripe_customer_id", sc_id)
                            .order("created_at", desc=True)
                            .execute()
                        )
                        for o in result.data or []:
                            if o.get("id") and o["id"] not in seen_ids:
                                seen_ids.add(o["id"])
                                orders_by_email.append(o)
                    except Exception:
                        pass
        # Orders tied to this Stripe account by subscription id even when stripe_customer_id was never stored.
        sub_ids = _stripe_subscription_ids_for_customer_ids(unique_sc_ids)
        if sub_ids:
            try:
                result = (
                    self.client.table(self.table)
                    .select("*")
                    .in_("stripe_subscription_id", sub_ids)
                    .order("created_at", desc=True)
                    .execute()
                )
                for row in result.data or []:
                    if row.get("id") and row["id"] not in seen_ids:
                        seen_ids.add(row["id"])
                        orders_by_email.append(row)
            except Exception:
                for sid in sub_ids:
                    try:
                        result = (
                            self.client.table(self.table)
                            .select("*")
                            .eq("stripe_subscription_id", sid)
                            .order("created_at", desc=True)
                            .execute()
                        )
                        for o in result.data or []:
                            if o.get("id") and o["id"] not in seen_ids:
                                seen_ids.add(o["id"])
                                orders_by_email.append(o)
                    except Exception:
                        pass
        orders_by_email.sort(key=lambda x: (x.get("created_at") or ""), reverse=True)
        return orders_by_email

    def get_by_stripe_session_id(self, stripe_session_id: str) -> Optional[Dict[str, Any]]:
        """Get order by Stripe checkout session id (for thank-you → intake redirect)."""
        if not stripe_session_id:
            return None
        result = self.client.table(self.table).select("*").eq("stripe_session_id", stripe_session_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def try_claim_checkout_confirmation_email(self, order_id: str) -> bool:
        """
        Atomically set checkout_confirmation_email_sent_at if still null.
        Returns True if this caller should send the post-checkout email; False if already sent/claimed.
        Fails open (returns True) on unexpected errors so checkout still works before DB migration.
        """
        if not order_id:
            return False
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            # count=exact → Content-Range so we know row count even when the response body is empty
            # (some stacks return minimal/empty bodies for PATCH; bool(result.data) alone then skips sends).
            result = (
                self.client.table(self.table)
                .update(
                    {"checkout_confirmation_email_sent_at": now_iso},
                    count=CountMethod.exact,
                )
                .eq("id", order_id)
                .is_("checkout_confirmation_email_sent_at", "null")
                .execute()
            )
            if result.data and len(result.data) > 0:
                return True
            c = getattr(result, "count", None)
            if isinstance(c, int) and c > 0:
                return True
            row = self.get_by_id(order_id)
            if row and row.get("checkout_confirmation_email_sent_at") is None:
                print(
                    f"[CaptionOrderService] try_claim: PATCH matched 0 rows but sent_at still null for order {order_id[:8]}... "
                    f"— proceeding with send anyway (set SUPABASE_SERVICE_ROLE_KEY to persist claim and avoid duplicate sends)."
                )
                return True
            return False
        except Exception as e:
            if _is_checkout_claim_column_missing(e):
                print(
                    "[CaptionOrderService] checkout_confirmation_email_sent_at column missing — run "
                    "database_caption_orders_checkout_email_dedupe.sql in Supabase; dedupe disabled until then."
                )
                return True
            print(f"[CaptionOrderService] try_claim_checkout_confirmation_email (non-fatal): {e!r}")
            return True

    def release_checkout_confirmation_email_claim(self, order_id: str) -> None:
        """Clear claim so a failed send can be retried (e.g. SendGrid error)."""
        if not order_id:
            return
        try:
            self.client.table(self.table).update({"checkout_confirmation_email_sent_at": None}).eq("id", order_id).execute()
        except Exception as e:
            if _is_checkout_claim_column_missing(e):
                return
            print(f"[CaptionOrderService] release_checkout_confirmation_email_claim (non-fatal): {e!r}")

    def update(self, order_id: str, updates: Dict[str, Any]) -> bool:
        """Update order (status, intake, captions_md)."""
        updates["updated_at"] = datetime.utcnow().isoformat()
        result = self.client.table(self.table).update(updates).eq("id", order_id).execute()
        return bool(result.data)

    def save_intake(self, order_id: str, intake: Dict[str, Any], scheduled_delivery_at: Optional[str] = None) -> bool:
        """Save intake and set status to intake_completed. Optional scheduled_delivery_at for upgrade-from-one-off."""
        updates = {"intake": intake, "status": "intake_completed"}
        if scheduled_delivery_at:
            updates["scheduled_delivery_at"] = scheduled_delivery_at
        return self.update(order_id, updates)

    def update_intake_only(self, order_id: str, intake: Dict[str, Any]) -> bool:
        """Update intake JSON without changing status or re-triggering generation."""
        return self.update(order_id, {"intake": intake})

    def set_generating(self, order_id: str) -> bool:
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.update(
            order_id,
            {"status": "generating", "delivery_last_attempt_at": now_iso},
        )

    def set_delivered(
        self,
        order_id: str,
        captions_md: str,
        stories_pdf_bytes: Optional[bytes] = None,
        captions_pdf_bytes: Optional[bytes] = None,
    ) -> bool:
        """Mark order delivered; optionally store PDF artifacts as base64 for reliable re-download/resend.
        For any order that already had a delivered pack, archives the previous snapshot (md + PDFs) into
        delivery_archive before overwriting — subscriptions and one-offs — so Account → History can list
        past deliveries until the user removes the order from History."""
        row = self.get_by_id(order_id) or {}
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        delivery_archive = coerce_json_list(row.get("delivery_archive"))
        prev_delivered = (row.get("delivered_at") or "").strip()
        prev_md = (row.get("captions_md") or "").strip()
        new_md = (captions_md or "").strip()
        did_archive_prior_pack = False
        # Renewals / redeliveries call set_generating() before AI; when set_delivered runs, status is
        # often "generating" while the row still holds the previous pack — archive must still run.
        st = (row.get("status") or "").strip().lower()
        status_allows_archive = st in ("delivered", "generating")
        # Always snapshot the previous pack into delivery_archive before overwriting the row — do not
        # require prev_md != new_md (identical regeneration would skip archive and collapse History).
        if prev_delivered and prev_md and new_md and status_allows_archive:
            entry: Dict[str, Any] = {
                "delivered_at": prev_delivered,
                "captions_md": prev_md,
                "include_stories": order_includes_stories_addon(row),
            }
            intake_prev = row.get("intake") if isinstance(row.get("intake"), dict) else {}
            bn_snap = (intake_prev.get("business_name") or "").strip()
            if bn_snap:
                entry["business_name"] = bn_snap[:200]
            cap_b64 = (row.get("captions_pdf_base64") or "").strip()
            st_b64 = (row.get("stories_pdf_base64") or "").strip()
            if cap_b64:
                entry["captions_pdf_base64"] = cap_b64
            if st_b64:
                entry["stories_pdf_base64"] = st_b64
            delivery_archive.append(entry)
            # Keep last N entries so History does not grow without bound (rare: many redeliveries)
            _ARCHIVE_MAX = 200
            if len(delivery_archive) > _ARCHIVE_MAX:
                delivery_archive = delivery_archive[-_ARCHIVE_MAX:]
            did_archive_prior_pack = True
        updates: Dict[str, Any] = {
            "status": "delivered",
            "captions_md": captions_md,
            "delivered_at": now_iso,
            "delivery_failure_count": 0,
            "delivery_last_error": None,
        }
        if did_archive_prior_pack:
            updates["delivery_archive"] = delivery_archive
        if captions_pdf_bytes is not None:
            try:
                updates["captions_pdf_base64"] = base64.b64encode(captions_pdf_bytes).decode("ascii")
            except Exception:
                pass
        if stories_pdf_bytes is not None:
            try:
                updates["stories_pdf_base64"] = base64.b64encode(stories_pdf_bytes).decode("ascii")
            except Exception:
                pass
        return self.update(order_id, updates)

    def append_pack_history(self, order_id: str, month_str: str, day_categories: list) -> bool:
        """Append one pack's day categories to pack_history (for subscription variety). day_categories: list of 30 strings."""
        row = self.get_by_id(order_id)
        if not row:
            return False
        history = coerce_json_list(row.get("pack_history"))
        entry = {"month": month_str, "day_categories": (day_categories or [])[:30]}
        history.append(entry)
        # Keep last 12 months to avoid unbounded growth
        if len(history) > 12:
            history = history[-12:]
        return self.update(order_id, {"pack_history": history})

    def set_failed(self, order_id: str) -> bool:
        return self.update(order_id, {"status": "failed"})

    def record_delivery_failure(self, order_id: str, error_message: str, *, max_error_len: int = 4000) -> bool:
        """Increment delivery_failure_count, store delivery_last_error, set status failed (auto-retry respects cap)."""
        row = self.get_by_id(order_id)
        if not row:
            return False
        n = int(row.get("delivery_failure_count") or 0) + 1
        err = (error_message or "").strip()
        if len(err) > max_error_len:
            err = err[: max_error_len - 3] + "..."
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.update(
            order_id,
            {
                "status": "failed",
                "delivery_failure_count": n,
                "delivery_last_error": err or None,
                "delivery_last_attempt_at": now_iso,
            },
        )

    def hide_from_history(self, order_id: str) -> bool:
        """Mark order as hidden so it no longer appears in account history (status -> hidden)."""
        return self.update(order_id, {"status": "hidden"})

    def delete_by_customer_email(self, email: str) -> bool:
        """Permanently delete all caption orders for this customer (for account deletion).
        Deletes by customer_email and by stripe_customer_id (catches orders from different checkout emails)."""
        if not email or "@" not in email:
            return False
        e = email.strip().lower()
        try:
            # Fetch orders first (before delete) to get stripe_customer_ids
            orders = self.get_by_customer_email(email)
            stripe_ids = [
                (o.get("stripe_customer_id") or "").strip()
                for o in orders
                if (o.get("stripe_customer_id") or "").strip()
            ]
            # Delete by customer_email
            self.client.table(self.table).delete().eq("customer_email", e).execute()
            # Also delete orders linked via same Stripe customer (may have different checkout email)
            for sc_id in stripe_ids:
                try:
                    self.client.table(self.table).delete().eq("stripe_customer_id", sc_id).execute()
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def add_to_deleted_blocklist(self, email: str) -> bool:
        """Add email to blocklist so reminder/marketing emails are never sent (for account deletion)."""
        if not email or "@" not in email:
            return False
        e = email.strip().lower()
        try:
            self.client.table("deleted_account_emails").insert({"email": e}).execute()
            return True
        except Exception:
            # Idempotent: duplicate email already in blocklist
            return True

    def remove_from_deleted_blocklist(self, email: str) -> bool:
        """Remove email from blocklist when they create a new order (resubscribe)."""
        if not email or "@" not in email:
            return False
        try:
            self.client.table("deleted_account_emails").delete().eq(
                "email", email.strip().lower()
            ).execute()
            return True
        except Exception:
            return False

    def get_deleted_account_emails(self) -> frozenset:
        """Return set of emails that must not receive any reminders (deleted accounts)."""
        try:
            result = self.client.table("deleted_account_emails").select("email").execute()
            return frozenset((r.get("email") or "").strip().lower() for r in (result.data or []) if (r.get("email") or "").strip())
        except Exception:
            return frozenset()

    def update_customer_email(self, old_email: str, new_email: str) -> bool:
        """Update customer_email on all caption orders for this customer (for email change)."""
        if not old_email or "@" not in old_email or not new_email or "@" not in new_email:
            return False
        try:
            self.client.table(self.table).update({
                "customer_email": new_email.strip().lower(),
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("customer_email", old_email.strip().lower()).execute()
            return True
        except Exception:
            return False

    def get_scheduled_delivery_orders_due(self) -> list:
        """Orders with intake completed, scheduled_delivery_at in the past. For upgrade-from-one-off first pack."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        result = self.client.table(self.table).select("*").eq(
            "status", "intake_completed"
        ).not_.is_("stripe_subscription_id", "null").execute()
        data = result.data or []
        out = []
        for row in data:
            sched = row.get("scheduled_delivery_at")
            if not sched:
                continue
            try:
                if isinstance(sched, str):
                    sched_dt = datetime.fromisoformat(sched.replace("Z", "+00:00"))
                else:
                    sched_dt = sched
                if sched_dt.tzinfo is None:
                    sched_dt = sched_dt.replace(tzinfo=timezone.utc)
                if sched_dt <= now:
                    out.append(row)
            except Exception:
                pass
        return out

    def get_orders_needing_first_delivery_recovery(self, limit: int = 8) -> list:
        """
        Orders that have intake but never got captions_md — e.g. failed email, dead thread, stuck generating.
        Caller should start _run_generation_and_deliver for each id (usually capped per run).
        """
        from services.caption_delivery_recovery import row_needs_first_delivery_retry

        try:
            # Include failed rows while delivery_failure_count is below cap (see row_needs_first_delivery_retry).
            result = self.client.table(self.table).select("*").in_(
                "status", ["intake_completed", "generating", "failed"]
            ).order("updated_at", desc=False).limit(120).execute()
        except Exception:
            return []
        rows = result.data or []
        out = []
        for row in rows:
            intake = row.get("intake")
            if not intake or not isinstance(intake, dict):
                continue
            if not (intake.get("business_name") or "").strip():
                continue
            if not row_needs_first_delivery_retry(row, intake_completed_grace_seconds=120):
                continue
            out.append(row)
            if len(out) >= limit:
                break
        return out

    def get_orders_needing_captions_only_salvage(self, limit: int = 5) -> list:
        """
        Failed first-pack orders where stories repeatedly failed and no captions were delivered.
        These can be retried in captions-only mode to avoid blocking core delivery.
        """
        try:
            result = (
                self.client.table(self.table)
                .select("*")
                .eq("status", "failed")
                .is_("captions_md", "null")
                .eq("stories_generation_status", "failed")
                .order("updated_at", desc=False)
                .limit(120)
                .execute()
            )
        except Exception:
            return []
        rows = result.data or []
        out = []
        for row in rows:
            intake = row.get("intake")
            if not intake or not isinstance(intake, dict):
                continue
            if not (intake.get("business_name") or "").strip():
                continue
            if not (row.get("stripe_session_id") or "").strip():
                continue
            out.append(row)
            if len(out) >= limit:
                break
        return out

    def get_active_subscription_orders(self) -> list:
        """Get caption orders that have an active Stripe subscription (for reminder emails)."""
        result = self.client.table(self.table).select(
            "id, token, customer_email, stripe_subscription_id, reminder_sent_period_end, reminder_opt_out"
        ).not_.is_("stripe_subscription_id", "null").execute()
        return result.data or []

    def get_awaiting_intake_orders(self) -> list:
        """Get recent orders that are still awaiting intake (for one-off intake reminders)."""
        result = self.client.table(self.table).select(
            "id, token, customer_email, status, created_at, stripe_subscription_id, intake, captions_md"
        ).eq("status", "awaiting_intake").execute()
        return result.data or []

    def get_by_stripe_subscription_id(self, stripe_subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get order by Stripe subscription id. Prefer newest row if duplicates exist (undefined order otherwise)."""
        if not stripe_subscription_id:
            return None
        result = (
            self.client.table(self.table)
            .select("*")
            .eq("stripe_subscription_id", stripe_subscription_id.strip())
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None

    def set_reminder_sent(self, order_id: str, period_end_ts: str) -> bool:
        """Record that we sent a reminder for this billing period."""
        return self.update(order_id, {"reminder_sent_period_end": period_end_ts})

    def get_one_off_orders_for_upgrade_reminder(self, days_before_end: int = 5) -> list:
        """
        One-off orders that are in the upgrade-reminder window: delivered_at + (30 - days_before_end) days
        is within the last 24 hours. E.g. days_before_end=5 => 25 days after delivery; 3 => 27 days.
        Excludes orders that already had the reminder sent or opted out.
        """
        # One-off = no stripe_subscription_id; must be delivered with delivered_at set
        result = self.client.table(self.table).select(
            "id, token, customer_email, delivered_at, platforms_count, selected_platforms, include_stories, currency, intake, upgrade_reminder_sent_at, upgrade_reminder_opt_out"
        ).is_("stripe_subscription_id", "null").eq("status", "delivered").not_.is_("delivered_at", "null").execute()
        rows = result.data or []
        now = datetime.now(timezone.utc)
        days_after_delivery = 30 - days_before_end  # 25 or 27
        # Send when delivered_at is in [now - 26d, now - 25d] so we send once "25 days after delivery"
        window_end = now - timedelta(days=days_after_delivery)
        window_start = now - timedelta(days=days_after_delivery + 1)
        out = []
        for o in rows:
            if o.get("upgrade_reminder_sent_at") or o.get("upgrade_reminder_opt_out"):
                continue
            raw = o.get("delivered_at")
            if not raw:
                continue
            try:
                if isinstance(raw, str):
                    delivered_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                else:
                    delivered_dt = raw
                if delivered_dt.tzinfo is None:
                    delivered_dt = delivered_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if window_start <= delivered_dt <= window_end:
                out.append(o)
        return out

    def set_upgrade_reminder_sent(self, order_id: str) -> bool:
        """Record that we sent the one-off upgrade reminder for this order."""
        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.update(order_id, {"upgrade_reminder_sent_at": now_iso})

    def set_upgrade_reminder_opt_out_by_token(self, token: str) -> bool:
        """Opt out of one-off upgrade reminders (unsubscribe). Returns True if order was found and updated."""
        order = self.get_by_token(token)
        if not order:
            return False
        return self.update(order["id"], {"upgrade_reminder_opt_out": True})
