"""
Main Flask application for Lumo 22 (30 Days Captions).
"""
import html
import os
import time
import json
import secrets
import threading
import traceback
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, make_response, session
from flask_cors import CORS
from config import Config
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Optional

from services.caption_order_service import order_includes_stories_addon

# One-time login tokens: when session cookie does not persist (e.g. proxy), redirect to /account?login_token=X
# so the account page can set session from the token and render (cookie is set in that response).
_login_tokens = {}  # token -> {"customer_id": str, "email": str, "expires": float}
_LOGIN_TOKEN_TTL = 120  # seconds


def _create_login_token(customer_id: str, email: str) -> str:
    token = secrets.token_urlsafe(32)
    _login_tokens[token] = {
        "customer_id": str(customer_id),
        "email": email,
        "expires": time.time() + _LOGIN_TOKEN_TTL,
    }
    return token


def _consume_login_token(token: str):
    if not token:
        return None
    data = _login_tokens.pop(token, None)
    if not data or data.get("expires", 0) < time.time():
        return None
    return data
from api.routes import api_bp
from api.webhooks import webhook_bp
from api.captions_routes import captions_bp
from api.auth_routes import (
    auth_bp,
    get_current_customer,
    get_template_current_customer,
    set_customer_session,
    invalidate_current_customer_cache,
)
from api.passkey_routes import passkey_bp
from api.billing_routes import billing_bp
from api.oauth_routes import oauth_bp, init_customer_oauth, google_oauth_redirect_uri
from services.login_guard import check_locked, record_failure, clear_failures

app = Flask(__name__)
app.config.from_object(Config)
app.jinja_env.globals["order_includes_stories"] = order_includes_stories_addon
if Config.is_production():
    app.config['SESSION_COOKIE_SECURE'] = True

if Config.is_production():
    _base = (Config.BASE_URL or "").strip().rstrip("/")
    if _base and not _base.startswith("http"):
        _base = "https://" + _base
    _cors_origins = list({o for o in [
        _base, "https://www.lumo22.com", "https://lumo22.com",
        "https://lumo-22-production.up.railway.app",
    ] if o and o.startswith("http")}) or ["https://www.lumo22.com", "https://lumo22.com"]
    CORS(app, origins=_cors_origins, supports_credentials=True)
else:
    CORS(app)

# Cache-bust static assets: include CSS mtime so updated files always get a new version after deploy
_css_mtime_for_version = None
try:
    _landing_css = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'css', 'landing.css')
    _css_mtime_for_version = int(os.path.getmtime(_landing_css)) if os.path.exists(_landing_css) else 0
except Exception:
    _css_mtime_for_version = 0
# Prefer Railway deployment ID so every deploy gets a new cache-buster; else ASSET_VERSION or timestamp+mtime
_asset_version = (
    os.environ.get('RAILWAY_DEPLOYMENT_ID')
    or os.environ.get('ASSET_VERSION')
    or (str(int(time.time())) + '-' + str(_css_mtime_for_version))
)

# #region agent log
_DEBUG_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cursor', 'debug.log')
def _debug_log(msg, data, hypothesis_id):
    try:
        os.makedirs(os.path.dirname(_DEBUG_LOG_PATH), exist_ok=True)
        with open(_DEBUG_LOG_PATH, 'a') as f:
            f.write(json.dumps({"timestamp": int(time.time() * 1000), "location": "app.py", "message": msg, "data": data, "hypothesisId": hypothesis_id}) + "\n")
    except Exception:
        pass
# #endregion

# #region agent log
try:
    _landing_css_path = os.path.join(app.root_path, 'static', 'css', 'landing.css')
    _css_mtime = int(os.path.getmtime(_landing_css_path)) if os.path.exists(_landing_css_path) else None
    _debug_log("app startup", {"asset_version": _asset_version, "landing_css_path": _landing_css_path, "landing_css_exists": os.path.exists(_landing_css_path), "landing_css_mtime": _css_mtime}, "H2")
except Exception as e:
    _debug_log("app startup error", {"error": str(e)}, "H2")
# #endregion

@app.after_request
def add_security_headers(response):
    """Add security headers for Lighthouse Best Practices."""
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def _request_public_hostname():
    """Hostname from Host header (strip port, trailing FQDN dot). Do not use X-Forwarded-Host — mis-set values could break www."""
    raw = (request.host or "").strip().lower()
    if not raw:
        return ""
    return raw.split(":")[0].rstrip(".")


@app.before_request
def redirect_bare_domain_to_www():
    """Redirect lumo22.com (no www) to www.lumo22.com.

    GoDaddy apex *forwarding* is skipped when DNS @ points straight at Railway; this keeps /captions etc. working.
    """
    if _request_public_hostname() != "lumo22.com":
        return None
    dest = "https://www.lumo22.com" + (request.full_path or "/")
    return redirect(dest, code=301)


@app.context_processor
def inject_asset_version():
    from datetime import datetime
    out = {'asset_version': _asset_version}
    out['today_str'] = datetime.utcnow().strftime('%d %B %Y')
    try:
        out['current_customer'] = get_template_current_customer()
    except Exception:
        out['current_customer'] = None
    try:
        out['oauth_google_enabled'] = Config.oauth_google_configured()
    except Exception:
        out['oauth_google_enabled'] = False
    return out

# Register blueprints
app.register_blueprint(api_bp)
app.register_blueprint(webhook_bp)
app.register_blueprint(captions_bp)
app.register_blueprint(auth_bp)
init_customer_oauth(app)
app.register_blueprint(oauth_bp)
app.register_blueprint(passkey_bp)
app.register_blueprint(billing_bp)

# Fail fast on mis-set AI_PROVIDER (e.g. API key in Railway variable) and enforce prod API keys.
# Runs under Gunicorn/Railway, not only `python app.py`.
try:
    Config.validate_ai_provider_env()
except ValueError as _ai_cfg_err:
    import sys
    print(f"[Config] {_ai_cfg_err}", file=sys.stderr)
    raise SystemExit(1) from _ai_cfg_err

# Optional AI_VENDOR=anthropic|openai (plain text) to double-check Railway; startup log for deploy visibility
Config.validate_ai_vendor_optional()
Config.log_ai_provider_summary()

# Captions pre-pack reminder: run daily at 9am UTC (no separate cron service needed)
def _start_captions_reminder_scheduler():
    # Only start in production (avoids apscheduler import in dev, no need locally)
    is_prod = (os.getenv("FLASK_ENV") or "").strip().lower() == "production"
    if not is_prod:
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        def run_reminders_job():
            with app.app_context():
                try:
                    from services.caption_reminder_service import run_reminders
                    r = run_reminders()
                    print(f"[Captions reminder] sent={r.get('sent', 0)} skipped={r.get('skipped', 0)} errors={r.get('errors', [])}")
                except Exception as e:
                    print(f"[Captions reminder] error: {e}")

        def run_stuck_delivery_job():
            """Retry first-pack generation when intake succeeded but email/PDF never landed."""
            with app.app_context():
                try:
                    from api.captions_routes import _run_scheduled_deliveries, _run_stuck_first_deliveries

                    sched_r = _run_scheduled_deliveries()
                    stuck_r = _run_stuck_first_deliveries(max_orders=3)
                    n_sched = sched_r.get("scheduled_deliveries_triggered", 0)
                    n_stuck = stuck_r.get("stuck_first_delivery_triggered", 0)
                    if n_sched or n_stuck:
                        print(
                            f"[Captions recovery] scheduled_deliveries={n_sched} "
                            f"stuck_first_delivery={n_stuck}"
                        )
                except Exception as e:
                    print(f"[Captions recovery] error: {e}")

        from datetime import datetime, timezone, timedelta
        from apscheduler.triggers.interval import IntervalTrigger

        sched = BackgroundScheduler(daemon=True)
        sched.add_job(run_reminders_job, CronTrigger(hour=9, minute=0, timezone="UTC"))
        # Heal stuck orders (background thread died, SendGrid fail, etc.) without waiting for manual cron
        sched.add_job(
            run_stuck_delivery_job,
            IntervalTrigger(minutes=10, timezone="UTC"),
            next_run_time=datetime.now(timezone.utc) + timedelta(seconds=60),
            id="captions_stuck_and_scheduled_delivery",
            replace_existing=True,
        )
        sched.start()
        print("[Captions reminder] scheduler started (daily 9am UTC + stuck-delivery recovery every 10 min)")
    except Exception as e:
        print(f"[Captions reminder] scheduler not started: {e}")

_start_captions_reminder_scheduler()

@app.route('/favicon.ico')
def favicon():
    """Serve logo as favicon."""
    return send_from_directory(os.path.join(app.root_path, 'static', 'images'), 'logo.png', mimetype='image/png')

@app.route('/')
def index():
    """Public landing page - businesses sign up here"""
    # #region agent log
    try:
        _p = os.path.join(app.root_path, 'static', 'css', 'landing.css')
        _m = int(os.path.getmtime(_p)) if os.path.exists(_p) else None
        _debug_log("index route", {"template": "landing.html", "asset_version": _asset_version, "landing_css_exists": os.path.exists(_p), "landing_css_mtime": _m}, "H1")
    except Exception:
        pass
    # #endregion
    return render_template(
        'landing.html',
        inactivity_logout=request.args.get('inactivity') == '1',
    )

@app.route('/debug-deploy')
def debug_deploy():
    """Return what this process is serving (template, asset_version, static file info). Requires ?secret=DEBUG_DEPLOY_SECRET when set."""
    debug_secret = os.environ.get('DEBUG_DEPLOY_SECRET', '').strip()
    if debug_secret:
        if request.args.get('secret', '').strip() != debug_secret:
            return jsonify({"error": "Unauthorized"}), 401
    elif Config.is_production():
        return jsonify({"error": "Not available"}), 404
    css_path = os.path.join(app.root_path, 'static', 'css', 'landing.css')
    exists = os.path.exists(css_path)
    mtime = None
    first_line = ""
    if exists:
        try:
            mtime = int(os.path.getmtime(css_path))
            with open(css_path, 'r') as f:
                first_line = (f.readline() or "").strip()[:80]
        except Exception as e:
            first_line = "read_error: " + str(e)[:60]
    return jsonify({
        "template_for_slash": "landing.html",
        "asset_version": _asset_version,
        "landing_css_exists": exists,
        "landing_css_mtime": mtime,
        "landing_css_first_line": first_line,
    })

# Display prices per currency for captions page (oneoff, sub, extra_oneoff, extra_sub, stories_oneoff, stories_sub)
CAPTIONS_DISPLAY_PRICES = {
    "gbp": {"symbol": "£", "oneoff": 97, "sub": 79, "extra_oneoff": 29, "extra_sub": 19, "stories_oneoff": 29, "stories_sub": 17},
    "usd": {"symbol": "$", "oneoff": 119, "sub": 99, "extra_oneoff": 35, "extra_sub": 24, "stories_oneoff": 35, "stories_sub": 21},
    "eur": {"symbol": "€", "oneoff": 109, "sub": 89, "extra_oneoff": 32, "extra_sub": 22, "stories_oneoff": 32, "stories_sub": 19},
}

def _format_checkout_money(symbol: str, amount) -> str:
    """Format amount with symbol; omit decimals when whole-number currency units."""
    try:
        x = float(amount)
    except (TypeError, ValueError):
        x = 0.0
    x = round(x * 100) / 100
    if abs(x - round(x)) < 0.001:
        return f"{symbol}{int(round(x))}"
    return f"{symbol}{x:.2f}"


@app.route('/captions')
def captions_page():
    """30 Days of Social Media Captions product page. Subscription and one-off options. Supports GBP, USD, EUR."""
    use_checkout_redirect = bool(Config.STRIPE_SECRET_KEY and Config.STRIPE_CAPTIONS_PRICE_ID)
    subscription_available = bool(
        Config.STRIPE_SECRET_KEY and getattr(Config, 'STRIPE_CAPTIONS_SUBSCRIPTION_PRICE_ID', None)
    )
    extra_oneoff = bool((getattr(Config, 'STRIPE_CAPTIONS_EXTRA_PLATFORM_PRICE_ID', None) or '').strip())
    extra_sub = bool((getattr(Config, 'STRIPE_CAPTIONS_EXTRA_PLATFORM_SUBSCRIPTION_PRICE_ID', None) or '').strip())
    supports_multi_platform = use_checkout_redirect and (extra_oneoff or (subscription_available and extra_sub))
    stories_oneoff = bool((getattr(Config, 'STRIPE_CAPTIONS_STORIES_PRICE_ID', None) or '').strip())
    stories_sub = bool((getattr(Config, 'STRIPE_CAPTIONS_STORIES_SUBSCRIPTION_PRICE_ID', None) or '').strip())
    stories_addon_available = stories_oneoff and stories_sub
    checkout_error = request.args.get('error', '').strip()
    # Multi-currency: show selector if USD and/or EUR prices are configured
    has_usd = bool((getattr(Config, 'STRIPE_CAPTIONS_PRICE_ID_USD', None) or '').strip())
    has_eur = bool((getattr(Config, 'STRIPE_CAPTIONS_PRICE_ID_EUR', None) or '').strip())
    currencies_available = [{"code": "gbp", "label": "GBP", "symbol": "£"}]
    if has_usd:
        currencies_available.append({"code": "usd", "label": "USD", "symbol": "$"})
    if has_eur:
        currencies_available.append({"code": "eur", "label": "EUR", "symbol": "€"})
    r = make_response(render_template(
        'captions.html',
        captions_payment_link=Config.CAPTIONS_PAYMENT_LINK,
        use_checkout_redirect=use_checkout_redirect,
        captions_subscription_available=subscription_available,
        supports_multi_platform=supports_multi_platform,
        stories_addon_available=stories_addon_available,
        checkout_error=checkout_error,
        currencies_available=currencies_available,
        captions_prices=CAPTIONS_DISPLAY_PRICES,
    ))
    r.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    r.headers['Pragma'] = 'no-cache'
    return r

def _is_safe_redirect_url(url: str) -> bool:
    """True if url is a same-origin URL or a path (e.g. /captions-intake?t=...)."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if url.startswith('/') and '//' not in url[:2]:
        return True
    if not url.startswith(('http://', 'https://')):
        return False
    base = (Config.BASE_URL or '').strip()
    if not base or not base.startswith('http'):
        return False
    from urllib.parse import urlparse
    try:
        next_parsed = urlparse(url)
        base_parsed = urlparse(base if base.startswith('http') else 'https://' + base)
        return next_parsed.netloc == base_parsed.netloc
    except Exception:
        return False


def _normalize_next_url(raw_next: str | None) -> str | None:
    """Decode once/twice if needed so /path style next URLs stay usable."""
    if not raw_next or not isinstance(raw_next, str):
        return None
    raw_next = raw_next.strip()
    if not raw_next:
        return None
    from urllib.parse import unquote
    decoded = raw_next
    for _ in range(2):
        if decoded.startswith(('/', 'http://', 'https://')):
            break
        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded
    return decoded


def _intake_missing_substantive_brief_fields(intake: dict | None) -> bool:
    """True when intake is empty or only checkout-seeded (e.g. business_name) without real brief answers.
    Used so one-off → subscription upgrade still pre-fills the full one-off brief when Stripe only stored a name."""
    if not intake or not isinstance(intake, dict):
        return True
    substantive = (
        "business_type",
        "offer_one_line",
        "audience_cares",
        "goal",
        "usual_topics",
        "voice_words",
        "audience",
        "launch_event_description",
    )
    return not any(str(intake.get(k) or "").strip() for k in substantive)


@app.route('/captions-intake')
def captions_intake_page():
    """Intake form for 30 Days Captions (sent to client after payment). Token in ?t= links form to order.
    Subscription orders require login; one-off and no-token access unchanged.
    Supports copy_from=TOKEN to pre-fill from another order (e.g. one-off → subscription)."""
    from datetime import datetime
    from api.auth_routes import get_current_customer
    token = request.args.get('t', '').strip()
    copy_from = request.args.get('copy_from', '').strip()
    existing_intake = {}
    platforms_count = 1
    selected_platforms = ""
    stories_paid = False
    is_oneoff = False
    order = None
    oneoff_consumed_by_subscription = False
    if token:
        try:
            from services.caption_order_service import CaptionOrderService
            from api.captions_routes import enrich_order_intake_from_checkout_session

            svc = CaptionOrderService()
            order = svc.get_by_token(token)
            if order:
                # Stripe metadata may arrive before webhook seeds DB — fetch session once so the form prefills on first paint.
                order = enrich_order_intake_from_checkout_session(svc, order)
                if order.get("intake"):
                    existing_intake = order.get("intake") or {}
                platforms_count = max(1, int(order.get("platforms_count", 1)))
                selected_platforms = (order.get("selected_platforms") or "").strip() or ""
                stories_paid = bool(order.get("include_stories"))
                is_oneoff = not bool((order.get("stripe_subscription_id") or "").strip())
                if is_oneoff and token:
                    oneoff_consumed_by_subscription = svc.has_subscription_upgraded_from_oneoff_token(token)
                # copy_from: only prefill when this order was explicitly upgraded from that one-off (one-off→subscription flow).
                # If account was deleted and user resubscribes, order has no upgraded_from_token so we do not prefill.
                # Also merge when Stripe only seeded business_name (existing_intake truthy but not a real brief).
                if (not existing_intake or _intake_missing_substantive_brief_fields(existing_intake)) and copy_from:
                    upgraded_from = (order.get("upgraded_from_token") or "").strip()
                    if upgraded_from and upgraded_from == copy_from:
                        src_order = svc.get_by_token(copy_from)
                        if src_order:
                            src_email = (src_order.get("customer_email") or "").strip().lower()
                            cur_email = (order.get("customer_email") or "").strip().lower()
                            if src_email and cur_email and src_email == cur_email:
                                src_i = src_order.get("intake") if isinstance(src_order.get("intake"), dict) else {}
                                existing_intake = {**src_i, **(existing_intake or {})}
                # Subscription upgraded from one-off: prefill from base order even without ?copy_from=…
                # (e.g. account "Edit form" only passes ?t=sub_token). Merge if intake empty or seed-only.
                if (not existing_intake or _intake_missing_substantive_brief_fields(existing_intake)) and (
                    order.get("stripe_subscription_id") or ""
                ).strip():
                    upgraded_from = (order.get("upgraded_from_token") or "").strip()
                    if upgraded_from:
                        src_order = svc.get_by_token(upgraded_from)
                        if src_order:
                            src_email = (src_order.get("customer_email") or "").strip().lower()
                            cur_email = (order.get("customer_email") or "").strip().lower()
                            if src_email and cur_email and src_email == cur_email:
                                src_i = src_order.get("intake") if isinstance(src_order.get("intake"), dict) else {}
                                existing_intake = {**src_i, **(existing_intake or {})}
        except Exception:
            pass
    # Subscription orders: require login and session email must match order
    if order and (order.get("stripe_subscription_id") or "").strip():
        from urllib.parse import quote
        customer = get_current_customer()
        order_email = (order.get("customer_email") or "").strip().lower()
        if not customer:
            return redirect(url_for('customer_login_page') + '?next=' + quote(request.url, safe=''))
        if (customer.get("email") or "").strip().lower() != order_email:
            return redirect(url_for('account_page'))
        # After auth only: copy one-off intake onto subscription row while awaiting_intake (no status change).
        # Account links often omit ?copy_from=; without this the subscription row can stay empty until a full submit.
        try:
            from services.caption_order_service import CaptionOrderService
            svc_auth = CaptionOrderService()
            order = svc_auth.get_by_token(token)
            if order and (order.get("status") or "").strip() == "awaiting_intake":
                db_intake = order.get("intake") if isinstance(order.get("intake"), dict) else {}
                src_intake = {}
                uft = (order.get("upgraded_from_token") or "").strip()
                if uft:
                    bo = svc_auth.get_by_token(uft)
                    if bo and isinstance(bo.get("intake"), dict):
                        be = (bo.get("customer_email") or "").strip().lower()
                        ce = (order.get("customer_email") or "").strip().lower()
                        if be and ce and be == ce:
                            src_intake = bo.get("intake") or {}
                merged = {**src_intake, **db_intake}
                # Upgrade flow: default the prefilled subscription intake to the plan they
                # actually chose at checkout (platform selection + stories add-on), so PDFs
                # reflect the upgraded configuration even if they don't edit these fields.
                selected_for_sub = (order.get("selected_platforms") or "").strip()
                if selected_for_sub:
                    merged["platform"] = selected_for_sub
                merged["include_stories"] = bool(order.get("include_stories"))
                # Always show merged in the form when we have a base one-off (fixes seed-only business_name on sub row).
                if src_intake:
                    existing_intake = merged
                # Persist full merge when the subscription row still lacks a real brief (e.g. only business_name from Stripe).
                oid = order.get("id")
                if oid and src_intake and _intake_missing_substantive_brief_fields(db_intake):
                    if svc_auth.update_intake_only(str(oid), merged):
                        order = svc_auth.get_by_token(token)
                        if order and isinstance(order.get("intake"), dict):
                            existing_intake = order["intake"]
        except Exception:
            pass
    return_url = request.args.get("return_url", "").strip()
    is_upgrade_flow = bool(return_url and "/account/upgrade" in return_url)
    # Hub flow: return may be Update preferences OR Manage subscription → get pack sooner checkout panel.
    _ru = return_url or ""
    is_prepare_pack_sooner_return = bool(
        "/account/prepare-pack-sooner" in _ru
        or (
            "/account/subscription" in _ru
            and "get_pack_sooner" in _ru
            and "order_token" in _ru
        )
    )
    account_hub_plan_picker = is_upgrade_flow or is_prepare_pack_sooner_return
    # Account hub (upgrade or prepare-pack-sooner): query params match the hub form before intake
    if account_hub_plan_picker and token:
        upgrade_stories = request.args.get("upgrade_stories", "").strip()
        if upgrade_stories == "0":
            stories_paid = False
        elif upgrade_stories == "1":
            stories_paid = True
    upgrade_selected = (request.args.get("selected", "").strip() if account_hub_plan_picker else "") or ""
    if account_hub_plan_picker and token:
        upgrade_platforms = request.args.get("platforms", "").strip()
        if upgrade_platforms:
            try:
                n = max(1, min(4, int(upgrade_platforms)))
                platforms_count = n
                if request.args.get("selected", "").strip():
                    selected_platforms = request.args.get("selected", "").strip()
            except ValueError:
                pass
    # Prefill platform from order (chosen at checkout) when they haven't saved intake yet
    prefilled_platform = (existing_intake.get("platform") or "").strip() if existing_intake else ""
    if order and (order.get("stripe_subscription_id") or "").strip() and (order.get("upgraded_from_token") or "").strip():
        selected_for_sub = (selected_platforms or "").strip()
        if selected_for_sub:
            prefilled_platform = selected_for_sub
    if not prefilled_platform and selected_platforms:
        prefilled_platform = selected_platforms
    # Checkout links often use ?platforms=1 without ?selected=; Stripe metadata then omits selected_platforms.
    if not prefilled_platform and order and platforms_count == 1:
        prefilled_platform = "Instagram & Facebook"
    if account_hub_plan_picker and upgrade_selected:
        prefilled_platform = upgrade_selected
    # Normalise legacy "Instagram" / "Facebook" to grouped "Instagram & Facebook"
    if prefilled_platform in ("Instagram", "Facebook"):
        prefilled_platform = "Instagram & Facebook"
    elif prefilled_platform and "," in prefilled_platform:
        parts = [p.strip() for p in prefilled_platform.split(",") if p.strip()]
        normalized = []
        seen = set()
        for p in parts:
            if p in ("Instagram", "Facebook"):
                p = "Instagram & Facebook"
            if p and p not in seen:
                seen.add(p)
                normalized.append(p)
        prefilled_platform = ", ".join(normalized)
    # For "Platform selection" (single-platform): use first platform so it preselects
    prefilled_primary = prefilled_platform.split(",")[0].strip() if prefilled_platform else ""
    if prefilled_primary in ("Instagram", "Facebook"):
        prefilled_primary = "Instagram & Facebook"
    now = datetime.utcnow()
    subscribe_url = None
    order_currency = "gbp"
    intake_add_platform_text = "+£29 one-off / +£19 monthly"
    intake_add_stories_text = "+£29 one-off / +£17 monthly"
    if order:
        order_currency = (order.get("currency") or "gbp").strip().lower()
        if order_currency not in ("gbp", "usd", "eur"):
            order_currency = "gbp"
        p = CAPTIONS_DISPLAY_PRICES.get(order_currency, CAPTIONS_DISPLAY_PRICES["gbp"])
        intake_add_platform_text = "+{symbol}{extra_oneoff} one-off / +{symbol}{extra_sub} monthly".format(symbol=p["symbol"], extra_oneoff=p["extra_oneoff"], extra_sub=p["extra_sub"])
        intake_add_stories_text = "+{symbol}{stories_oneoff} one-off / +{symbol}{stories_sub} monthly".format(symbol=p["symbol"], stories_oneoff=p["stories_oneoff"], stories_sub=p["stories_sub"])
    if token and is_oneoff:
        from urllib.parse import urlencode
        sub_params = {"copy_from": token, "platforms": platforms_count}
        if selected_platforms:
            sub_params["selected"] = selected_platforms
        if stories_paid:
            sub_params["stories"] = "1"
        if order_currency in ("gbp", "usd", "eur"):
            sub_params["currency"] = order_currency
        subscribe_url = "/captions-checkout-subscription?" + urlencode(sub_params)
    if oneoff_consumed_by_subscription:
        subscribe_url = None
    order_status = (order.get("status") or "").strip() if order else ""
    # Checkout seeds minimal intake (e.g. business_name) before the customer fills the form; "returning"
    # is determined by order status, not by whether intake dict is non-empty.
    intake_returning_editor = bool(order and order_status and order_status != "awaiting_intake")
    view_raw = (request.args.get("view") or "").strip().lower()
    pending_oneoff_intake = bool(order and is_oneoff and order_status == "awaiting_intake")
    # e.g. Account → Upgrade → "Edit form": show full editable form + POST, then continue to checkout (not review-only → Stripe).
    edit_intake_before_subscribe = (request.args.get("edit") or "").strip().lower() in ("1", "true", "yes")
    # Completed one-off (not yet subscribed): form is read-only; review step confirms → subscription checkout (no POST).
    oneoff_subscribe_checkout_mode = bool(
        token
        and order
        and is_oneoff
        and not oneoff_consumed_by_subscription
        and order_status
        and order_status != "awaiting_intake"
    ) and not edit_intake_before_subscribe
    intake_view_only = bool(
        (
            view_raw in ("1", "true", "yes")
            or oneoff_consumed_by_subscription
            or oneoff_subscribe_checkout_mode
        )
        and token
        and order
        and is_oneoff
        and not pending_oneoff_intake
    )
    from urllib.parse import quote as _url_quote
    account_upgrade_base_url = (
        "/account/upgrade?base=" + _url_quote(token, safe="")
        if token and is_oneoff and not oneoff_consumed_by_subscription
        else ""
    )
    r = make_response(
        render_template(
            "captions_intake.html",
            intake_token=token,
            existing_intake=existing_intake,
            platforms_count=platforms_count,
            prefilled_platform=prefilled_platform,
            prefilled_primary=prefilled_primary,
            stories_paid=stories_paid,
            is_oneoff=is_oneoff,
            selected_platforms=selected_platforms,
            subscribe_url=subscribe_url,
            now=now,
            return_url=return_url,
            order_currency=order_currency,
            intake_add_platform_text=intake_add_platform_text,
            intake_add_stories_text=intake_add_stories_text,
            is_upgrade_flow=is_upgrade_flow,
            is_prepare_pack_sooner_return=is_prepare_pack_sooner_return,
            account_hub_plan_picker=account_hub_plan_picker,
            intake_returning_editor=intake_returning_editor,
            intake_view_only=intake_view_only,
            account_upgrade_base_url=account_upgrade_base_url,
            oneoff_upgraded_to_subscription=oneoff_consumed_by_subscription,
            oneoff_subscribe_checkout_mode=oneoff_subscribe_checkout_mode,
            edit_intake_before_subscribe=edit_intake_before_subscribe,
        )
    )
    r.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    r.headers['Pragma'] = 'no-cache'
    return r

@app.route('/captions-thank-you')
def captions_thank_you_page():
    """Thank-you page after Stripe payment (set as redirect URL in Stripe)"""
    return render_template('captions_thank_you.html')


@app.route('/captions-deliver-helper')
def captions_deliver_helper_page():
    """Simple page: paste intake or thank-you link, click button to run deliver-test and see result."""
    return render_template('captions_deliver_helper.html')

def _parse_platforms_from_request():
    """Parse platforms from request args; clamp 1-4."""
    try:
        n = int(request.args.get("platforms", 1))
        return max(1, min(4, n))
    except (TypeError, ValueError):
        return 1


@app.route('/captions-checkout')
def captions_checkout_page():
    """Pre-checkout page: agree to T&Cs then continue to Stripe (one-off). Supports GBP, USD, EUR."""
    from urllib.parse import urlencode, quote
    platforms = _parse_platforms_from_request()
    selected = (request.args.get("selected") or request.args.get("selected_platforms") or "").strip()
    stories = request.args.get("stories", "").strip().lower() in ("1", "true", "yes", "on")
    currency = (request.args.get("currency") or "gbp").strip().lower()
    if currency not in CAPTIONS_DISPLAY_PRICES:
        currency = "gbp"
    prices = CAPTIONS_DISPLAY_PRICES[currency]
    selected_count = len([p.strip() for p in selected.split(",") if p.strip()]) if selected else 0
    platforms_invalid = platforms > 1 and selected_count != platforms
    params = {"platforms": platforms, "currency": currency}
    if selected:
        params["selected"] = selected
    if stories:
        params["stories"] = "1"
    ref = (request.args.get("ref") or "").strip()
    if ref:
        params["ref"] = ref
    business_name = (request.args.get("business_name") or "").strip()
    business_key = (request.args.get("business_key") or "").strip()
    if business_name:
        params["business_name"] = business_name
    if business_key:
        params["business_key"] = business_key
    q = urlencode(params)
    api_url = f"/api/captions-checkout?{q}" if not platforms_invalid else None
    total = prices["oneoff"] + (platforms - 1) * prices["extra_oneoff"] + (prices["stories_oneoff"] if stories else 0)
    sym = prices["symbol"]
    captions_prefill = "?" + q + "#pricing"
    back_to_captions_url = "/captions" + captions_prefill
    add_stories_url = ("/captions?stories=1&platforms=" + str(platforms) + "&currency=" + currency + ("&selected=" + quote(selected) if selected else "") + "#pricing") if not stories else None
    add_platforms_url = ("/captions" + captions_prefill) if platforms < 4 else None
    return render_template(
        'captions_checkout.html',
        platforms=platforms,
        selected=selected,
        stories=stories,
        api_url=api_url,
        total_oneoff=total,
        checkout_total_display=_format_checkout_money(sym, total),
        referral_discount_applies=False,
        currency_symbol=sym,
        platforms_invalid=platforms_invalid,
        add_stories_url=add_stories_url,
        add_platforms_url=add_platforms_url,
        back_to_captions_url=back_to_captions_url,
        checkout_business_name=business_name,
    )


@app.route('/captions-checkout-subscription')
def captions_checkout_subscription_page():
    """Pre-checkout page for Captions subscription: agree to T&Cs then continue to Stripe. Supports GBP, USD, EUR.
    Accepts copy_from=TOKEN to pass through to Stripe metadata for one-off → subscription flow.
    All subscription checkouts (new and upgrade from one-off) require an account before payment (signup first, then log in if already registered)."""
    from urllib.parse import urlencode, quote
    copy_from = (request.args.get("copy_from") or "").strip()
    current_customer = get_current_customer()
    if not current_customer:
        signup_url = url_for("customer_signup_page") + "?next=" + quote(request.full_path or "/captions-checkout-subscription", safe="")
        return redirect(signup_url)
    platforms = _parse_platforms_from_request()
    selected = (request.args.get("selected") or request.args.get("selected_platforms") or "").strip()
    stories = request.args.get("stories", "").strip().lower() in ("1", "true", "yes", "on")
    reminders_on = request.args.get("form_reminders", "1").strip().lower() not in ("0", "false", "no", "off")
    currency = (request.args.get("currency") or "gbp").strip().lower()
    if currency not in CAPTIONS_DISPLAY_PRICES:
        currency = "gbp"
    prices = CAPTIONS_DISPLAY_PRICES[currency]
    selected_count = len([p.strip() for p in selected.split(",") if p.strip()]) if selected else 0
    platforms_invalid = platforms > 1 and selected_count != platforms
    params = {"platforms": platforms, "currency": currency}
    if selected:
        params["selected"] = selected
    if stories:
        params["stories"] = "1"
    if reminders_on:
        params["form_reminders"] = "1"
    else:
        params["form_reminders"] = "0"
    ref = (request.args.get("ref") or "").strip()
    if ref:
        params["ref"] = ref
    business_name = (request.args.get("business_name") or "").strip()
    business_key = (request.args.get("business_key") or "").strip()
    first_charge_date_str = None
    can_get_pack_now = False
    valid_copy_from_order = False
    if copy_from:
        try:
            from services.caption_order_service import CaptionOrderService
            from datetime import datetime, timedelta, timezone

            one_off = CaptionOrderService().get_by_token(copy_from)
            if one_off:
                one_off_email = (one_off.get("customer_email") or "").strip().lower()
                cust_email = (current_customer.get("email") or "").strip().lower()
                if not one_off_email or not cust_email or one_off_email != cust_email:
                    one_off = None
            if one_off:
                valid_copy_from_order = True
                params["copy_from"] = copy_from
                if not business_name:
                    intake = one_off.get("intake") if isinstance(one_off.get("intake"), dict) else {}
                    business_name = (intake.get("business_name") or "").strip() or business_name
                is_delivered = bool(one_off.get("status") == "delivered" or one_off.get("delivered_at"))
                can_get_pack_now = is_delivered
                raw = one_off.get("delivered_at") or one_off.get("updated_at") or one_off.get("created_at")
                if is_delivered and raw:
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00")) if isinstance(raw, str) else raw
                    if getattr(dt, "tzinfo", None) is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    first_charge_date_str = (dt + timedelta(days=30)).strftime("%d %B %Y")
        except Exception:
            pass
    if business_name:
        params["business_name"] = business_name
    if business_key:
        params["business_key"] = business_key
    q = urlencode(params)
    api_url = f"/api/captions-checkout-subscription?{q}" if not platforms_invalid else None
    total = prices["sub"] + (platforms - 1) * prices["extra_sub"] + (prices["stories_sub"] if stories else 0)
    sym = prices["symbol"]
    captions_prefill = "?" + q + "#pricing"
    back_to_captions_url = "/captions" + captions_prefill
    if not stories:
        add_stories_params = "stories=1&platforms=" + str(platforms) + "&currency=" + currency
        if selected:
            add_stories_params += "&selected=" + quote(selected)
        if valid_copy_from_order:
            add_stories_params += "&copy_from=" + quote(copy_from)
        if business_name:
            add_stories_params += "&business_name=" + quote(business_name)
        if business_key:
            add_stories_params += "&business_key=" + quote(business_key)
        add_stories_url = "/captions?" + add_stories_params + "#pricing"
    else:
        add_stories_url = None
    add_platforms_url = ("/captions" + captions_prefill) if platforms < 4 else None
    return render_template(
        'captions_checkout_subscription.html',
        platforms=platforms,
        selected=selected,
        stories=stories,
        api_url=api_url,
        total_sub=total,
        referral_discount_applies=False,
        sub_first_month_display=None,
        sub_thereafter_display=None,
        currency_symbol=sym,
        platforms_invalid=platforms_invalid,
        add_stories_url=add_stories_url,
        add_platforms_url=add_platforms_url,
        back_to_captions_url=back_to_captions_url,
        is_upgrade_from_oneoff=valid_copy_from_order,
        first_charge_date=first_charge_date_str,
        can_get_pack_now=can_get_pack_now,
        form_reminders_on=reminders_on,
        checkout_business_name=business_name,
    )


@app.route('/privacy')
def privacy_page():
    """Privacy policy page."""
    return render_template('privacy.html')

@app.route('/terms')
def terms_page():
    """Terms & Conditions."""
    return render_template('terms.html')

@app.route('/plans')
def plans_page():
    """Redirect to Captions pricing."""
    return redirect(url_for('captions_page') + '#pricing')

@app.route('/digital-front-desk')
def digital_front_desk_page():
    """DFD shelved — redirect to Captions."""
    return redirect(url_for('captions_page'))


@app.route('/book')
def booking_page():
    """Redirect to Captions (DFD shelved)."""
    return redirect(url_for('captions_page'))


@app.route('/book-demo')
def booking_demo_page():
    """DFD discontinued — redirect to Captions."""
    return redirect(url_for('captions_page'))


@app.route('/website-chat')
def website_chat_page():
    """Redirect to Captions (DFD/Chat shelved)."""
    return redirect(url_for('captions_page'))


@app.route('/website-chat-success')
def website_chat_success_page():
    """Redirect to Captions (DFD/Chat shelved)."""
    return redirect(url_for('captions_page'))

def customer_login_required(f):
    """Redirect to login if customer not in session. Accepts ?login_token= for one-time login when cookie does not persist."""
    @wraps(f)
    def decorated(*args, **kwargs):
        customer = get_current_customer()
        if not customer and request.args.get("login_token"):
            data = _consume_login_token(request.args.get("login_token", "").strip())
            if data:
                try:
                    from services.customer_auth_service import CustomerAuthService
                    _c = CustomerAuthService().get_by_email(data["email"])
                    if _c and str(_c.get("id")) == str(data["customer_id"]):
                        set_customer_session(_c)
                    else:
                        session.permanent = True
                        session["customer_id"] = data["customer_id"]
                        session["customer_email"] = data["email"]
                        session["auth_version"] = 0
                        invalidate_current_customer_cache()
                except Exception:
                    session.permanent = True
                    session["customer_id"] = data["customer_id"]
                    session["customer_email"] = data["email"]
                    session["auth_version"] = 0
                    invalidate_current_customer_cache()
                # Render the page in this response so session cookie is set here (no second request needed)
                return f(*args, **kwargs)
        if not customer:
            return redirect(url_for('customer_login_page') + '?next=' + request.url)
        return f(*args, **kwargs)
    return decorated


@app.route('/captions-upgrade')
@customer_login_required
def captions_upgrade_page():
    """Dedicated upgrade page: add platforms or Story Ideas to an existing subscription. Requires login.
    Query: token (required), platforms (target count 1–4), stories (0|1), return_url (optional)."""
    token = (request.args.get("token") or "").strip()
    return_url = (request.args.get("return_url") or "").strip()
    if not token:
        return redirect(url_for("account_page"))
    try:
        from services.caption_order_service import CaptionOrderService
        from api.billing_routes import _subscription_monthly_price
        svc = CaptionOrderService()
        order = svc.get_by_token(token)
    except Exception:
        return redirect(url_for("account_page"))
    if not order:
        return redirect(url_for("account_page"))
    sub_id = (order.get("stripe_subscription_id") or "").strip()
    if not sub_id:
        return redirect(url_for("captions_page"))
    customer = get_current_customer()
    order_email = (order.get("customer_email") or "").strip().lower()
    if not customer or (customer.get("email") or "").strip().lower() != order_email:
        return redirect(url_for("account_page"))
    current_platforms = max(1, int(order.get("platforms_count", 1)))
    current_stories = bool(order.get("include_stories"))
    currency = (order.get("currency") or "gbp").strip().lower()
    if currency not in ("gbp", "usd", "eur"):
        currency = "gbp"
    platforms_param = request.args.get("platforms", "").strip()
    stories_param = (request.args.get("stories") or "").strip().lower() in ("1", "true", "yes", "on")
    new_platforms = current_platforms
    new_stories = current_stories
    if platforms_param:
        try:
            new_platforms = max(1, min(4, int(platforms_param)))
        except (TypeError, ValueError):
            pass
    if stories_param:
        new_stories = True
    is_platform_upgrade = new_platforms > current_platforms
    is_stories_upgrade = new_stories and not current_stories
    if not is_platform_upgrade and not is_stories_upgrade:
        if return_url and return_url.startswith("/"):
            return redirect(return_url)
        intake_url = url_for("captions_intake_page", t=token)
        return redirect(intake_url)
    try:
        _, new_total = _subscription_monthly_price(currency, new_platforms, new_stories)
        _, old_total = _subscription_monthly_price(currency, current_platforms, current_stories)
    except Exception:
        new_total = 79 + (new_platforms - 1) * 19 + (17 if new_stories else 0)
        old_total = 79 + (current_platforms - 1) * 19 + (17 if current_stories else 0)
    symbols = {"gbp": "£", "usd": "$", "eur": "€"}
    symbol = symbols.get(currency, "£")
    if not return_url or not return_url.startswith("/"):
        return_url = url_for("captions_intake_page", t=token)
    upgrade_type = "platforms" if is_platform_upgrade else "stories"
    if is_platform_upgrade and is_stories_upgrade:
        upgrade_type = "both"
    extra_platforms = new_platforms - current_platforms
    return render_template(
        "captions_upgrade.html",
        order_token=token,
        new_platforms=new_platforms,
        new_stories=new_stories,
        current_platforms=current_platforms,
        current_stories=current_stories,
        extra_platforms=extra_platforms,
        add_stories=is_stories_upgrade,
        price_symbol=symbol,
        new_monthly=new_total,
        return_url=return_url,
        upgrade_type=upgrade_type,
    )


@app.route('/signup')
def customer_signup_page():
    """Signup for Lumo 22 customers (Captions). Accepts next= and email= for upgrade flow."""
    next_url = _normalize_next_url(request.args.get('next')) or None
    prefilled_email = (request.args.get('email') or '').strip() or None
    signup_referral = (request.args.get('ref') or '').strip() or None
    return render_template(
        'customer_signup.html',
        next_url=next_url,
        prefilled_email=prefilled_email,
        signup_referral=signup_referral,
    )


@app.route('/login', methods=['GET', 'POST'])
def customer_login_page():
    """Login for Lumo 22 customers (DFD, Chat, Captions). GET shows form; POST does login and redirects."""
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = (request.form.get('password') or '').strip()
        next_url = _normalize_next_url(request.form.get('next') or request.args.get('next')) or '/account'
        client_ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()
        if not email or not password:
            return render_template('customer_login.html', login_error='Please enter your email and password.', next_url=next_url)
        is_locked, retry_after = check_locked(email, client_ip)
        if is_locked:
            mins = max(1, int((retry_after + 59) // 60))
            return render_template('customer_login.html', login_error=f'Too many failed attempts. Try again in about {mins} minute(s).', next_url=next_url)
        try:
            from services.customer_auth_service import CustomerAuthService
            svc = CustomerAuthService()
            customer = svc.get_by_email(email)
            if not customer or not svc.verify_password(customer, password):
                record_failure(email, client_ip)
                return render_template('customer_login.html', login_error='Invalid email or password.', next_url=next_url)
            if not customer.get('email_verified', True):
                return render_template('customer_login.html', login_error='Please verify your email before logging in. Check your inbox or request a new verification link.', needs_verification=True, verification_email=email, next_url=next_url)
            svc.update_last_login(customer['id'])
            clear_failures(email, client_ip)
            set_customer_session(customer)
            # One-time token so account page can set session even if cookie from this response does not persist
            login_token = _create_login_token(customer['id'], customer['email'])
            account_url = url_for('account_page') + '?login_token=' + login_token
            # Redirect to requested next URL if safe (same origin or path), else account
            redirect_url = account_url
            if next_url and next_url != '/account' and _is_safe_redirect_url(next_url):
                redirect_url = next_url if next_url.startswith(('http://', 'https://')) else (request.url_root.rstrip('/') + next_url)
            return render_template('login_success.html', next_url=redirect_url)
        except Exception:
            return render_template('customer_login.html', login_error='Something went wrong. Please try again.', next_url=next_url)
    next_url = _normalize_next_url(request.args.get('next')) or '/account'
    prefilled_email = (request.args.get('email') or '').strip() or None
    oauth_error_message = None
    oe = (request.args.get('oauth_error') or '').strip()
    if oe:
        _oem = {
            "state": "That sign-in link expired or was invalid. Please try again.",
            "email": "We could not read a verified email from the provider. Try again or use email and password.",
            "profile": "We could not load your profile from the provider. Try again.",
            "unverified": "That account’s email is not verified with the provider. Try another method.",
            "link": "This sign-in is already linked to a different account. Contact hello@lumo22.com if you need help.",
            "exists": "An account with this email already exists. Log in with your password, then use Continue with Google to link that sign-in.",
            "registered": "That Google account is already registered. Log in with Continue with Google.",
            "create": "We could not create your account. Try again or use email sign-up.",
            "disabled": "That sign-in method is not available yet.",
            "denied": "Sign-in was cancelled.",
            "token": "Sign-in with the provider did not complete. Try again.",
            "callback": "Sign-in with Google did not complete. Try again.",
        }
        oauth_error_message = _oem.get(oe) or "Sign-in did not complete. Try again or use email and password."
    return render_template(
        'customer_login.html',
        next_url=next_url,
        prefilled_email=prefilled_email,
        oauth_error_message=oauth_error_message,
    )


@app.route('/forgot-password')
def forgot_password_page():
    """Forgot password: enter email, receive reset link."""
    return render_template('forgot_password.html')


@app.route('/reset-password')
def reset_password_page():
    """Reset password: token from email, set new password."""
    token = request.args.get('token', '').strip()
    return render_template('reset_password.html', token=token)


@app.route('/verify-email')
def verify_email_page():
    """Verify email: token from signup welcome email. Marks email verified; next= preserved for upgrade flow.
    On success with next=, redirect to login?next= so user goes straight to login then checkout."""
    from urllib.parse import quote
    token = request.args.get('token', '').strip()
    next_url = request.args.get('next', '').strip() or None
    if next_url and not _is_safe_redirect_url(next_url):
        next_url = None
    if not token:
        return render_template('verify_email.html', success=False, error="No verification link found. Please request a new one.", next_url=next_url)
    try:
        from services.customer_auth_service import CustomerAuthService
        svc = CustomerAuthService()
        ok, customer, err = svc.confirm_email_verification(token)
        if not ok:
            return render_template('verify_email.html', success=False, error=err, next_url=next_url)
        if next_url and next_url != '/account':
            return redirect(url_for("customer_login_page") + "?next=" + quote(next_url, safe=""))
        return render_template('verify_email.html', success=True, next_url=next_url)
    except Exception as e:
        import logging
        logging.exception("verify_email failed: %s", e)
        return render_template('verify_email.html', success=False, error="Something went wrong. Please try again or contact hello@lumo22.com.", next_url=next_url)


@app.route('/change-email-confirm')
def change_email_confirm_page():
    """Confirm email change: token from email, update email and redirect to account."""
    token = request.args.get('token', '').strip()
    if not token:
        return render_template('change_email_confirm.html', success=False, error="No verification link found. Please request a new one from your account.")
    try:
        from services.customer_auth_service import CustomerAuthService
        from services.caption_order_service import CaptionOrderService
        svc = CustomerAuthService()
        ok, new_email, old_email, err = svc.confirm_email_change(token)
        if not ok:
            return render_template('change_email_confirm.html', success=False, error=err or "Invalid or expired link.")
        # Update caption_orders for this customer
        co_svc = CaptionOrderService()
        co_svc.update_customer_email(old_email, new_email)
        # Update Stripe customer email if we have stripe_customer_id
        try:
            orders = co_svc.get_by_customer_email(new_email)
            stripe_customer_ids = set()
            for o in orders or []:
                cid = (o.get("stripe_customer_id") or "").strip()
                if cid:
                    stripe_customer_ids.add(cid)
            if stripe_customer_ids and Config.STRIPE_SECRET_KEY:
                import stripe
                stripe.api_key = Config.STRIPE_SECRET_KEY
                for cid in stripe_customer_ids:
                    try:
                        stripe.Customer.modify(cid, email=new_email)
                    except Exception:
                        pass
        except Exception:
            pass
        # Log them in with new email
        customer = svc.get_by_email(new_email)
        if customer:
            set_customer_session(customer)
        return redirect(url_for('account_page') + '?email_changed=1', code=302)
    except Exception as e:
        import logging
        logging.exception("change_email_confirm failed: %s", e)
        return render_template('change_email_confirm.html', success=False, error="Something went wrong. Please try again or contact hello@lumo22.com.")


_ACCOUNT_SECTIONS = frozenset(
    {"information", "history", "edit-form", "upgrade", "subscription", "refer", "prepare-pack-sooner"}
)


def _prepare_pack_sooner_hub_context(customer: dict) -> tuple:
    """
    Validate ?order_token= for /account/prepare-pack-sooner.
    Returns (prep dict or None, error_code or None). prep keys: token, label.
    """
    from services.caption_order_service import CaptionOrderService

    token = (request.args.get("order_token") or "").strip()
    email = (customer.get("email") or "").strip().lower()
    if not token:
        return None, "missing_token"
    if not email or "@" not in email:
        return None, "invalid_session"
    try:
        svc = CaptionOrderService()
        order = svc.get_by_token(token)
    except Exception:
        return None, "load_error"
    if not order:
        return None, "not_found"
    order_email = (order.get("customer_email") or "").strip().lower()
    if order_email != email:
        return None, "forbidden"
    if not (order.get("stripe_subscription_id") or "").strip():
        return None, "not_subscription"
    if not order.get("intake"):
        return None, "no_intake"
    intake = order.get("intake") or {}
    biz = _safe_str(intake.get("business_name"))
    label = biz.title() if biz else "Your subscription"
    platforms_count = max(1, min(4, _safe_int(order.get("platforms_count"), 1)))
    selected_platforms = (order.get("selected_platforms") or "").strip() or ""
    selected_platforms_list = [p.strip() for p in selected_platforms.split(",") if p.strip()]
    include_stories = bool(order.get("include_stories"))
    align_stories_to_captions = bool(intake.get("align_stories_to_captions"))
    currency = (order.get("currency") or "gbp").strip().lower()
    if currency not in ("gbp", "usd", "eur"):
        currency = "gbp"
    return {
        "token": token,
        "order_id": str(order.get("id") or ""),
        "label": label,
        "platforms_count": platforms_count,
        "selected_platforms": selected_platforms,
        "selected_platforms_list": selected_platforms_list,
        "include_stories": include_stories,
        "align_stories_to_captions": align_stories_to_captions,
        "currency": currency,
    }, None


def _referral_share_mailto_href(base_url: str, code: str) -> str:
    """Pre-built mailto: URI for refer-a-friend (avoids JS mailto issues; works as a real link)."""
    from urllib.parse import quote

    b = (base_url or "").strip().rstrip("/")
    c = (code or "").strip()
    if not b or not c:
        return ""
    link_home = f"{b}/"
    subject = "10% off Lumo 22 — your friend invited you"
    body = (
        "Hi,\n\n"
        "I'm inviting you to try Lumo 22 — 30 days of social media captions (and optional story ideas) written for your business.\n\n"
        "What this is: Lumo 22's refer-a-friend offer.\n"
        "The discount: 10% off your first purchase — applied only when you enter the code below on the Stripe payment page under “Add promotion code”. Visiting a link does not apply the discount by itself.\n"
        "Our site (optional):\n"
        f"{link_home}\n\n"
        f"Your code (enter at checkout): {c}\n\n"
        "—"
    )
    return "mailto:?subject=" + quote(subject, safe="") + "&body=" + quote(body, safe="")


def _referral_share_sms_href(base_url: str, code: str) -> str:
    """Pre-built sms: URI with one link + code and short context."""
    from urllib.parse import quote

    b = (base_url or "").strip().rstrip("/")
    c = (code or "").strip()
    if not b or not c:
        return ""
    link_home = f"{b}/"
    text = (
        "Hi — Lumo 22: 30 days of social captions. 10% off first purchase — enter this code at checkout under Add promotion code: "
        f"{c} "
        f"(Opening a link alone doesn’t apply the discount.) {link_home}"
    )
    return "sms:?body=" + quote(text, safe="")


def _one_off_eligible_for_upgrade_base_dropdown(o: dict) -> bool:
    """Show in subscription upgrade 'base pack' UI only after one-off intake is submitted (prefill is real).
    Delivered is not required—intake_completed / generating / delivered / failed (post-intake) all qualify."""
    st = (o.get("status") or "").strip().lower()
    if not st or st == "awaiting_intake" or st == "hidden":
        return False
    return True


def _edit_form_pdf_delivered_sort_ts(o: dict) -> str:
    """Timestamp string for sorting by last captions PDF delivery; empty if not delivered yet."""
    t = (o.get("delivered_at") or "").strip()
    if t:
        return t
    if (o.get("status") or "").strip().lower() == "delivered":
        return (o.get("updated_at") or o.get("created_at") or "").strip() or ""
    return ""


def _edit_form_row_sort_ts(o: dict) -> str:
    """Single sort key for Edit form: last PDF delivery time, or order created_at if no PDF yet."""
    pdf_ts = _edit_form_pdf_delivered_sort_ts(o)
    if pdf_ts:
        return pdf_ts
    return (o.get("created_at") or "").strip() or ""


def _order_hidden_from_account(o: dict) -> bool:
    """True if customer removed this pack from History (hide-pack); exclude from Edit form list."""
    return (o.get("status") or "").strip().lower() == "hidden"


def _history_delivered_orders(caption_orders: list) -> list:
    """
    Account → History: rows with a delivered pack (PDFs / download links).
    Primary rule: status == delivered. Also include rows that have delivered_at + captions_md
    (same signal as has_delivered_pack elsewhere) so a pack still appears if status was mis-set in DB.
    Excludes hidden (user deleted from History).
    """
    out = []
    for o in caption_orders or []:
        if _order_hidden_from_account(o):
            continue
        st = (o.get("status") or "").strip().lower()
        has_md = bool((o.get("captions_md") or "").strip())
        has_delivered_ts = bool(o.get("delivered_at"))
        if st == "delivered" or (has_delivered_ts and has_md):
            out.append(o)
    out.sort(
        key=lambda x: (x.get("delivered_at") or x.get("updated_at") or x.get("created_at") or ""),
        reverse=True,
    )
    return out


def _history_order_activity_ts(o: dict) -> str:
    """Most recent delivery / activity first when sorting subscription order rows."""
    return (o.get("delivered_at") or o.get("updated_at") or o.get("created_at") or "").strip()


def _history_pack_entries_for_order(o: dict, *, include_current: bool) -> list:
    """
    Build history list rows for one caption_orders row: each delivery_archive slice + optionally current pack.
    Downloads resolve via (token, archive_index) — each row keeps its own token.
    """
    from services.caption_order_service import (
        archive_entry_includes_stories,
        coerce_json_list,
        order_includes_stories_addon,
    )

    token = (o.get("token") or "").strip()
    if not token:
        return []
    arch = coerce_json_list(o.get("delivery_archive"))
    packs = []
    for i, a in enumerate(arch):
        if not isinstance(a, dict):
            continue
        packs.append(
            {
                "order": o,
                "token": token,
                "archive_index": i,
                "delivered_at": (a.get("delivered_at") or "").strip(),
                "include_stories": archive_entry_includes_stories(a),
                "business_name": ((a.get("business_name") or "").strip() or None),
            }
        )
    if include_current:
        packs.append(
            {
                "order": o,
                "token": token,
                "archive_index": None,
                "delivered_at": (o.get("delivered_at") or "").strip(),
                "include_stories": order_includes_stories_addon(o),
                "business_name": None,
            }
        )
    return packs


def _dedupe_duplicate_subscription_current_lines(entries: list) -> list:
    """
    When two caption_orders rows share stripe_subscription_id and represent the same delivery
    (same delivered_at + same captions snapshot), keep one line — typically the row with the latest
    updated_at. Distinct delivery dates (e.g. March on a stale row + June on the active row) are kept.
    """
    from collections import defaultdict

    buckets: dict = defaultdict(list)
    for i, e in enumerate(entries):
        if e.get("archive_index") is not None:
            continue
        o = e.get("order") or {}
        sid = (o.get("stripe_subscription_id") or "").strip()
        if not sid:
            continue
        da = (e.get("delivered_at") or "").strip()[:19]
        if not da:
            continue
        md = (o.get("captions_md") or "").strip()
        md_head = md[:400] if md else ""
        buckets[(sid, da, md_head)].append(i)
    drop: set = set()
    for _key, idxs in buckets.items():
        if len(idxs) <= 1:
            continue
        # Keep single best row per duplicate snapshot (newest activity wins)
        def _row_sort_key(ii: int) -> tuple:
            o = entries[ii].get("order") or {}
            ts = (o.get("updated_at") or o.get("created_at") or "").strip()
            oid = str(o.get("id") or "")
            return (ts, oid)

        idxs_sorted = sorted(idxs, key=_row_sort_key, reverse=True)
        drop.update(idxs_sorted[1:])
    if not drop:
        return entries
    return [e for i, e in enumerate(entries) if i not in drop]


def _history_delivered_entries(caption_orders: list) -> list:
    """
    Account → History: one row per delivered pack with downloadable PDFs.
    Past subscription months live in delivery_archive (each index); the order row holds the latest pack.
    List every archive entry plus the current row — no cap from pack_history. Newest first.

    If multiple caption_orders rows share the same stripe_subscription_id (duplicates / migrations),
    list archives from every row and include each row's current pack so prior months are not lost.
    Dedupe only when two rows expose the same subscription delivery snapshot (same time + same content).
    """
    rows = _history_delivered_orders(caption_orders)
    by_sub: dict = {}
    no_sub: list = []
    for o in rows:
        sid = (o.get("stripe_subscription_id") or "").strip()
        if sid:
            by_sub.setdefault(sid, []).append(o)
        else:
            no_sub.append(o)

    out = []
    for o in no_sub:
        out.extend(_history_pack_entries_for_order(o, include_current=True))

    for _sid, group in by_sub.items():
        if len(group) == 1:
            out.extend(_history_pack_entries_for_order(group[0], include_current=True))
            continue
        group = sorted(group, key=_history_order_activity_ts, reverse=True)
        for o in group:
            out.extend(_history_pack_entries_for_order(o, include_current=True))

    out = _dedupe_duplicate_subscription_current_lines(out)

    def _history_entry_sort_key(entry: dict) -> str:
        d = (entry.get("delivered_at") or "").strip()
        # Missing dates last when sorting newest-first
        return d if d else "1970-01-01T00:00:00Z"

    out.sort(key=_history_entry_sort_key, reverse=True)
    return out


def _safe_int(val, default: int = 0) -> int:
    """Coerce to int without raising. DB JSON may have null or bad strings (e.g. platforms_count)."""
    try:
        if val is None or val == "":
            return int(default)
        return int(val)
    except (TypeError, ValueError):
        return int(default)


def _safe_str(val) -> str:
    """String for display/keys; DB JSON may store numbers or null where we expect text."""
    if val is None:
        return ""
    return str(val).strip()


def _account_context_fallback(customer: dict, exc=None) -> dict:
    """Minimal account shell so /account can render if building full context raises."""
    if exc is not None:
        traceback.print_exc()
        print(f"[account] context fallback after: {exc!r}")
    base = (Config.BASE_URL or request.url_root or "").strip().rstrip("/")
    if base and not base.startswith("http"):
        base = "https://" + base
    rc = _safe_str(customer.get("referral_code"))
    ref_coupon = (getattr(Config, "STRIPE_REFERRAL_COUPON_ID", None) or "").strip()
    ref_secret = (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip()
    return {
        "customer": customer,
        "caption_orders": [],
        "current_intake_order": None,
        "subscription_billing": {"payment_methods": [], "subscription_payment_methods": {}, "subscription_pricing": {}},
        "billing_accounts": [],
        "subscribe_options": [],
        "subscribe_url": None,
        "subscribe_business_name": None,
        "one_off_orders": [],
        "one_off_upgrade_options": [],
        "edit_form_orders": [],
        "edit_form_has_subscriptions": False,
        "edit_form_has_oneoffs": False,
        "captions_prices": CAPTIONS_DISPLAY_PRICES,
        "base_url": base,
        "referral_code": rc,
        "referral_discount_credits": _safe_int(customer.get("referral_discount_credits"), 0),
        "referral_mailto_href": _referral_share_mailto_href(base, rc) if rc else "",
        "referral_sms_href": _referral_share_sms_href(base, rc) if rc else "",
        "referral_discount_configured": bool(ref_coupon and ref_secret),
        "referral_stripe_promo_ok": bool(_safe_str(customer.get("stripe_referral_promotion_code_id"))),
        "account_resubscribe_mode": False,
        "account_load_error": True,
        "defer_stripe_billing": False,
        "edit_form_needs_deferred_billing": False,
        "history_delivered_orders": [],
        "history_delivered_entries": [],
    }


def _account_context(section: Optional[str] = None):
    """Load customer and account data for dashboard. Returns dict for template."""
    customer = get_current_customer()
    if not customer:
        return None
    try:
        return _account_context_build(customer, section=section)
    except Exception as e:
        return _account_context_fallback(customer, e)


def _account_resolve_referral_customer(customer: dict, *, stripe_promotion_sync: bool = True):
    """Ensure referral code; refresh customer row only if DB/Stripe updated it. Runs in parallel with Stripe billing."""
    from services.customer_auth_service import CustomerAuthService

    cid = str(customer.get("id") or "").strip()
    if not cid:
        return None, customer

    # Session row is from get_current_customer() — skip extra Supabase when nothing can change this request.
    if not stripe_promotion_sync:
        existing = (customer.get("referral_code") or "").strip()
        if existing:
            return existing, customer
    else:
        rc = (customer.get("referral_code") or "").strip()
        promo = (customer.get("stripe_referral_promotion_code_id") or "").strip()
        if rc and promo:
            return rc, customer

    auth_svc = CustomerAuthService()
    code, need_refresh = auth_svc.ensure_referral_code(
        cid, stripe_promotion_sync=stripe_promotion_sync
    )
    if need_refresh:
        refreshed = auth_svc.get_by_id(cid)
        if refreshed:
            customer = refreshed
    return code, customer


# Stripe subscription/card data for account — loaded async after HTML when DEFER_ACCOUNT_STRIPE_BILLING is True.
DEFER_ACCOUNT_STRIPE_BILLING = True

_ACCOUNT_SUB_PAUSE_FALLBACK = {
    "paused": False,
    "resumes_at": None,
    "cancel_at_period_end": False,
    "cancelled_now": False,
    "ends_at": None,
    "next_pack_due": None,
}


def _init_subscription_pause_placeholders(caption_orders: list) -> None:
    """Before Stripe runs: set neutral subscription_pause on each row (same shape as _load_account_stripe_subscription_data)."""
    for o in caption_orders or []:
        sid = (o.get("stripe_subscription_id") or "").strip()
        o["subscription_pause"] = None if not sid else dict(_ACCOUNT_SUB_PAUSE_FALLBACK)


def _account_merge_order_rows(caption_orders: list) -> None:
    """Merge intake from one-off into subscription rows and set has_delivered_pack (no Stripe)."""
    by_token = {
        (o.get("token") or "").strip(): o
        for o in caption_orders
        if (o.get("token") or "").strip()
    }
    for o in caption_orders:
        if not (o.get("stripe_subscription_id") or "").strip():
            continue
        intake = dict(o.get("intake") or {})
        if _safe_str(intake.get("business_name")):
            continue
        uft = (o.get("upgraded_from_token") or "").strip()
        if not uft:
            continue
        base = by_token.get(uft)
        if not base or not isinstance(base.get("intake"), dict):
            continue
        bi = base["intake"]
        for k, v in bi.items():
            if v is not None and v != "" and not intake.get(k):
                intake[k] = v
        o["intake"] = intake
    for o in caption_orders:
        delivered_self = bool(o.get("status") == "delivered" or o.get("delivered_at"))
        upgraded_from = (o.get("upgraded_from_token") or "").strip()
        delivered_base = False
        if upgraded_from:
            base = by_token.get(upgraded_from)
            delivered_base = bool(base and (base.get("status") == "delivered" or base.get("delivered_at")))
        o["has_delivered_pack"] = bool(delivered_self or delivered_base)


def _account_fetch_merged_orders_and_stripe_billing(customer: dict):
    """Load orders, merge rows, run Stripe — used by /api/account/billing-data."""
    email = (customer.get("email") or "").strip()
    from services.caption_order_service import CaptionOrderService

    co_svc = CaptionOrderService()
    caption_orders = co_svc.get_by_customer_email_including_stripe_customer(email)
    _account_merge_order_rows(caption_orders)
    subscription_billing = _load_account_stripe_subscription_data(caption_orders)
    return caption_orders, subscription_billing


def _account_context_build(customer: dict, section: Optional[str] = None) -> dict:
    """Assemble template context; may raise — caller wraps with fallback."""
    email = customer.get("email", "")
    caption_orders = []
    referral_code = None
    account_orders_ok = False
    subscription_billing = None
    sync_referral_promo = (section or "information") == "refer"
    defer = DEFER_ACCOUNT_STRIPE_BILLING
    try:
        from services.caption_order_service import CaptionOrderService

        co_svc = CaptionOrderService()
        caption_orders = co_svc.get_by_customer_email_including_stripe_customer(email)
        if defer:
            _init_subscription_pause_placeholders(caption_orders)
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut_ref = pool.submit(
                    _account_resolve_referral_customer,
                    customer,
                    stripe_promotion_sync=sync_referral_promo,
                )
                try:
                    _account_merge_order_rows(caption_orders)
                finally:
                    referral_code, customer = fut_ref.result()
            subscription_billing = {
                "payment_methods": [],
                "subscription_payment_methods": {},
                "subscription_pricing": {},
            }
        else:
            with ThreadPoolExecutor(max_workers=2) as pool:
                fut_billing = pool.submit(_load_account_stripe_subscription_data, caption_orders)
                fut_ref = pool.submit(
                    _account_resolve_referral_customer,
                    customer,
                    stripe_promotion_sync=sync_referral_promo,
                )
                try:
                    _account_merge_order_rows(caption_orders)
                finally:
                    subscription_billing = fut_billing.result()
                    referral_code, customer = fut_ref.result()
        account_orders_ok = True
    except Exception as e:
        print(f"[account] Error loading data: {e}")
        if subscription_billing is None:
            subscription_billing = _load_account_stripe_subscription_data(caption_orders)
            referral_code = None
    current_intake_order = None
    if caption_orders:
        sub_orders = [o for o in caption_orders if (o.get("stripe_subscription_id") or "").strip()]
        current_intake_order = sub_orders[0] if sub_orders else caption_orders[0]

    if subscription_billing is None:
        subscription_billing = {
            "payment_methods": [],
            "subscription_payment_methods": {},
            "subscription_pricing": {},
        }

    # Billing accounts: one per unique stripe_customer_id among subscription orders
    # Each has { stripe_customer_id, label, order_token } so Manage billing can be scoped
    billing_accounts = []
    seen_cids = set()
    sub_orders = [o for o in caption_orders if (o.get("stripe_subscription_id") or "").strip()]
    for o in sub_orders:
        cid = (o.get("stripe_customer_id") or "").strip()
        if not cid or cid in seen_cids:
            continue
        seen_cids.add(cid)
        intake = o.get("intake") or {}
        biz = _safe_str(intake.get("business_name"))
        created_raw = o.get("created_at")
        created_short = str(created_raw)[:10] if created_raw is not None else ""
        label = biz.title() if biz else (created_short or "Subscription")
        billing_accounts.append({
            "stripe_customer_id": cid,
            "label": label,
            "order_token": (o.get("token") or "").strip(),
        })

    # Upgrade options for one-off customers: one entry per one-off order so they can choose which pack to base a subscription on.
    # Omit one-offs already linked as upgraded_from_token on a subscription row (that upgrade path is done).
    # Omit one-offs removed from History (status hidden)—same as Edit form.
    subscribe_options = []
    one_off_orders = [o for o in caption_orders if not (o.get("stripe_subscription_id") or "").strip()]
    # Suppress the base one-off pack from upgrade/resubscribe lists while a subscription row exists for it,
    # or while the former subscription row (cancelled) still references it — avoids duplicate choices.
    upgraded_from_tokens = {
        (o.get("upgraded_from_token") or "").strip()
        for o in caption_orders
        if (o.get("upgraded_from_token") or "").strip()
        and (
            (o.get("stripe_subscription_id") or "").strip()
            or bool(o.get("subscription_cancelled_at"))
        )
    }
    one_off_orders = [
        o for o in one_off_orders
        if (o.get("token") or "").strip() not in upgraded_from_tokens
        and not _order_hidden_from_account(o)
    ]
    one_off_upgrade_options = [o for o in one_off_orders if _one_off_eligible_for_upgrade_base_dropdown(o)]
    if one_off_upgrade_options:
        from urllib.parse import urlencode
        for o in one_off_upgrade_options:
            token = (o.get("token") or "").strip()
            if not token:
                continue
            intake = o.get("intake") or {}
            _bn = _safe_str(intake.get("business_name"))
            business_name = _bn or None
            platforms_count = max(1, _safe_int(o.get("platforms_count"), 1))
            selected_platforms = (o.get("selected_platforms") or "").strip() or ""
            stories_paid = bool(o.get("include_stories"))
            sub_params = {"copy_from": token, "platforms": platforms_count}
            if selected_platforms:
                sub_params["selected"] = selected_platforms
            if stories_paid:
                sub_params["stories"] = "1"
            currency = (o.get("currency") or "gbp").strip().lower()
            if currency in ("gbp", "usd", "eur"):
                sub_params["currency"] = currency
            url = "/captions-checkout-subscription?" + urlencode(sub_params)
            subscribe_options.append({
                "url": url,
                "business_name": business_name,
                "is_resubscribe": bool(o.get("subscription_cancelled_at")),
            })
    # Backward compatibility: single upgrade link (most recent one-off)
    subscribe_url = subscribe_options[0]["url"] if subscribe_options else None
    subscribe_business_name = subscribe_options[0]["business_name"] if subscribe_options else None

    # Edit form: subs + eligible one-offs; omit packs hidden from History; sort by last PDF time else created_at
    edit_form_subs = [
        o for o in caption_orders
        if (o.get("stripe_subscription_id") or "").strip() and not _order_hidden_from_account(o)
    ]
    edit_form_orders = edit_form_subs + [o for o in one_off_orders if (o.get("token") or "").strip()]
    edit_form_orders.sort(key=_edit_form_row_sort_ts, reverse=True)
    edit_form_has_subscriptions = any((o.get("stripe_subscription_id") or "").strip() for o in edit_form_orders)
    edit_form_has_oneoffs = any(not (o.get("stripe_subscription_id") or "").strip() for o in edit_form_orders)
    # Deferred billing fetch is only needed for subscription rows (pause/cancel badges). Skip when Edit form is one-offs only.
    edit_form_needs_deferred_billing = any(
        (o.get("stripe_subscription_id") or "").strip() for o in edit_form_orders
    )

    base = (Config.BASE_URL or request.url_root or "").strip().rstrip("/")
    if base and not base.startswith("http"):
        base = "https://" + base
    rc = (referral_code or "").strip()
    ref_coupon = (getattr(Config, "STRIPE_REFERRAL_COUPON_ID", None) or "").strip()
    ref_secret = (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip()
    referral_discount_configured = bool(ref_coupon and ref_secret)
    referral_stripe_promo_ok = bool(_safe_str(customer.get("stripe_referral_promotion_code_id")))
    # True when every subscribe/upgrade link is for a pack that used to be on a subscription (Stripe sub deleted).
    account_resubscribe_mode = bool(subscribe_options) and all(
        (x.get("is_resubscribe") for x in subscribe_options)
    )
    history_delivered_orders = _history_delivered_orders(caption_orders)
    history_delivered_entries = _history_delivered_entries(caption_orders)
    return {
        "customer": customer,
        "caption_orders": caption_orders,
        "history_delivered_orders": history_delivered_orders,
        "history_delivered_entries": history_delivered_entries,
        "current_intake_order": current_intake_order,
        "subscription_billing": subscription_billing,
        "billing_accounts": billing_accounts,
        "subscribe_options": subscribe_options,
        "subscribe_url": subscribe_url,
        "subscribe_business_name": subscribe_business_name,
        "one_off_orders": one_off_orders,
        "one_off_upgrade_options": one_off_upgrade_options,
        "edit_form_orders": edit_form_orders,
        "edit_form_has_subscriptions": edit_form_has_subscriptions,
        "edit_form_has_oneoffs": edit_form_has_oneoffs,
        "edit_form_needs_deferred_billing": edit_form_needs_deferred_billing,
        "captions_prices": CAPTIONS_DISPLAY_PRICES,
        "base_url": base,
        "referral_code": rc,
        "referral_discount_credits": _safe_int(customer.get("referral_discount_credits"), 0),
        "referral_mailto_href": _referral_share_mailto_href(base, rc) if rc else "",
        "referral_sms_href": _referral_share_sms_href(base, rc) if rc else "",
        "referral_discount_configured": referral_discount_configured,
        "referral_stripe_promo_ok": referral_stripe_promo_ok,
        "account_resubscribe_mode": account_resubscribe_mode,
        "account_load_error": False,
        "defer_stripe_billing": DEFER_ACCOUNT_STRIPE_BILLING,
    }


_ACCOUNT_SUB_RETRIEVE_CACHE = {}
_ACCOUNT_SUB_RETRIEVE_LOCK = threading.Lock()
_ACCOUNT_SUB_RETRIEVE_TTL_SEC = 45.0


def _account_stripe_subscription_retrieve_cached(stripe_mod, sub_id: str):
    """
    Subscription.retrieve with a short process-local TTL so /account + /api/account/billing-data
    (or quick navigation between them) do not each pay full Stripe latency for every sub.
    Failures are not cached so transient errors retry on the next request.
    """
    now = time.monotonic()
    with _ACCOUNT_SUB_RETRIEVE_LOCK:
        hit = _ACCOUNT_SUB_RETRIEVE_CACHE.get(sub_id)
        if hit is not None:
            ts, obj = hit
            if (now - ts) < _ACCOUNT_SUB_RETRIEVE_TTL_SEC:
                return sub_id, obj
    try:
        obj = stripe_mod.Subscription.retrieve(
            sub_id,
            expand=["default_payment_method", "items.data.price", "discount.coupon"],
        )
    except Exception:
        return sub_id, None
    with _ACCOUNT_SUB_RETRIEVE_LOCK:
        _ACCOUNT_SUB_RETRIEVE_CACHE[sub_id] = (now, obj)
    return sub_id, obj


def invalidate_account_stripe_subscription_cache(subscription_id: str) -> None:
    """
    Drop cached Stripe Subscription.retrieve for this id so the next account / billing-data
    request reflects Subscription.modify (plan changes, get-pack-sooner anchor, etc.).
    """
    sid = (subscription_id or "").strip()
    if not sid:
        return
    with _ACCOUNT_SUB_RETRIEVE_LOCK:
        _ACCOUNT_SUB_RETRIEVE_CACHE.pop(sid, None)


def _subscription_pricing_from_stripe_sub(sub, sub_id, out: dict) -> None:
    """Fill subscription_payment_methods and subscription_pricing for one subscription into out."""
    pm = sub.get("default_payment_method")
    if pm and isinstance(pm, dict):
        card = pm.get("card") or {}
        out["subscription_payment_methods"][sub_id] = {
            "id": pm.get("id"),
            "brand": (card.get("brand") or "card").capitalize(),
            "last4": card.get("last4") or "****",
        }
    else:
        out["subscription_payment_methods"][sub_id] = None

    try:
        items = ((sub.get("items") or {}).get("data") or [])
        subtotal_minor = 0
        currency = "gbp"
        for item in items:
            if not isinstance(item, dict):
                continue
            price = item.get("price") or {}
            unit_amount = int(price.get("unit_amount") or 0)
            qty = int(item.get("quantity") or 1)
            subtotal_minor += max(0, unit_amount) * max(1, qty)
            if price.get("currency"):
                currency = str(price.get("currency")).strip().lower()
        symbols = {"gbp": "£", "usd": "$", "eur": "€"}
        symbol = symbols.get(currency, "£")
        standard_monthly = round(subtotal_minor / 100.0, 2)
        effective_monthly = standard_monthly
        discount_type = None
        discount_percent = None
        discount_amount = None
        discount_duration = None
        discount_end = None

        discount = sub.get("discount")
        if isinstance(discount, dict):
            coupon = discount.get("coupon") or {}
            percent_off = coupon.get("percent_off")
            amount_off = coupon.get("amount_off")
            if percent_off is not None:
                try:
                    discount_percent = float(percent_off)
                    effective_monthly = round(
                        max(0.0, standard_monthly * (1.0 - (discount_percent / 100.0))),
                        2,
                    )
                    discount_type = "percent"
                except Exception:
                    pass
            elif amount_off is not None:
                try:
                    discount_amount = round(float(amount_off) / 100.0, 2)
                    effective_monthly = round(
                        max(0.0, standard_monthly - float(discount_amount)),
                        2,
                    )
                    discount_type = "amount"
                except Exception:
                    pass
            discount_duration = (coupon.get("duration") or "").strip().lower() or None
            discount_end = discount.get("end")

        out["subscription_pricing"][sub_id] = {
            "currency": currency,
            "symbol": symbol,
            "standard_monthly": standard_monthly,
            "effective_monthly": effective_monthly,
            "discount_type": discount_type,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "discount_duration": discount_duration,
            "discount_end": discount_end,
        }
    except Exception:
        out["subscription_pricing"][sub_id] = None


def _load_account_stripe_subscription_data(caption_orders):
    """
    Build payment_methods list and per-subscription billing for account page.
    One Stripe Subscription.retrieve per unique subscription id (shared with pause badges).
    Sets o['subscription_pause'] on each caption order row.
    Returns:
    {
      "payment_methods": [{ id, brand, last4 }],
      "subscription_payment_methods": { sub_id: { id, brand, last4 } },
      "subscription_pricing": { sub_id: { ... } },
    }.
    """
    from api.captions_routes import _pause_info_from_subscription
    from api.stripe_utils import is_valid_stripe_subscription_id

    out = {"payment_methods": [], "subscription_payment_methods": {}, "subscription_pricing": {}}
    orders = caption_orders or []
    for o in orders:
        sid = (o.get("stripe_subscription_id") or "").strip()
        o["subscription_pause"] = None if not sid else dict(_ACCOUNT_SUB_PAUSE_FALLBACK)

    if not orders or not getattr(Config, "STRIPE_SECRET_KEY", None):
        return out

    stripe_customer_id = None
    for o in orders:
        cid = (o.get("stripe_customer_id") or "").strip()
        if cid:
            stripe_customer_id = cid
            break

    try:
        import stripe

        stripe.api_key = Config.STRIPE_SECRET_KEY

        unique_sub_ids = []
        seen = set()
        for o in orders:
            sub_id = (o.get("stripe_subscription_id") or "").strip()
            if not sub_id or not is_valid_stripe_subscription_id(sub_id) or sub_id in seen:
                continue
            seen.add(sub_id)
            unique_sub_ids.append(sub_id)

        def _list_payment_methods():
            return stripe.PaymentMethod.list(customer=stripe_customer_id, type="card")

        def _retrieve_subscription(sub_id: str):
            return _account_stripe_subscription_retrieve_cached(stripe, sub_id)

        # Saved cards list is only used on the Pause/manage UI next to subscription rows; skip an extra
        # Stripe round trip for one-off-only customers (no subscription ids).
        list_saved_cards = bool(stripe_customer_id and unique_sub_ids)

        subs_by_id = {}
        workers = min(25, max(1, (1 if list_saved_cards else 0) + len(unique_sub_ids)))
        if workers > 1 and (list_saved_cards or unique_sub_ids):
            with ThreadPoolExecutor(max_workers=workers) as pool:
                pm_future = pool.submit(_list_payment_methods) if list_saved_cards else None
                sub_futures = [pool.submit(_retrieve_subscription, sid) for sid in unique_sub_ids]
                if pm_future:
                    try:
                        pm_list = pm_future.result()
                        for pm in (pm_list.data or []):
                            card = (pm.get("card") or {})
                            out["payment_methods"].append({
                                "id": pm.get("id"),
                                "brand": (card.get("brand") or "card").capitalize(),
                                "last4": card.get("last4") or "****",
                            })
                    except Exception:
                        pass
                for fut in sub_futures:
                    sid, sub = fut.result()
                    subs_by_id[sid] = sub
        else:
            if list_saved_cards:
                try:
                    pm_list = _list_payment_methods()
                    for pm in (pm_list.data or []):
                        card = (pm.get("card") or {})
                        out["payment_methods"].append({
                            "id": pm.get("id"),
                            "brand": (card.get("brand") or "card").capitalize(),
                            "last4": card.get("last4") or "****",
                        })
                except Exception:
                    pass
            for sub_id in unique_sub_ids:
                sid, sub = _retrieve_subscription(sub_id)
                subs_by_id[sid] = sub

        for o in orders:
            sub_id = (o.get("stripe_subscription_id") or "").strip()
            if not sub_id:
                o["subscription_pause"] = None
                continue
            sub = subs_by_id.get(sub_id)
            if sub is not None:
                o["subscription_pause"] = _pause_info_from_subscription(sub)
            elif is_valid_stripe_subscription_id(sub_id):
                o["subscription_pause"] = dict(_ACCOUNT_SUB_PAUSE_FALLBACK)

        for sub_id in unique_sub_ids:
            sub = subs_by_id.get(sub_id)
            if sub is None:
                out["subscription_payment_methods"][sub_id] = None
                out["subscription_pricing"][sub_id] = None
                continue
            try:
                _subscription_pricing_from_stripe_sub(sub, sub_id, out)
            except Exception:
                out["subscription_payment_methods"][sub_id] = None
                out["subscription_pricing"][sub_id] = None
    except Exception:
        pass
    return out


@app.route('/account/change-password')
@customer_login_required
def account_change_password_page():
    """Logged in: enter current password and new password (not the email reset flow)."""
    if not get_current_customer():
        return redirect(url_for('customer_login_page'))
    return render_template('change_password_logged_in.html')


@app.route("/api/account/referral-stripe-sync", methods=["POST"])
def referral_stripe_sync_api():
    """
    Logged-in: re-run Stripe promotion code create/reconcile for refer-a-friend.
    Use when account shows 'could not be linked to the payment page' but STRIPE_REFERRAL_COUPON_ID is set.
    """
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "linked": False, "error": "sign_in_required"}), 401
    try:
        from services.customer_auth_service import CustomerAuthService
        from services.stripe_referral_promotion import ensure_stripe_promotion_code_for_customer

        auth = CustomerAuthService()
        cid = str(customer.get("id") or "").strip()
        if not cid:
            return jsonify({"ok": False, "linked": False, "error": "invalid_session"}), 400
        auth.ensure_referral_code(cid)
        fresh = auth.get_by_id(cid)
        if not fresh:
            return jsonify({"ok": False, "linked": False, "error": "customer_not_found"}), 404
        ensure_stripe_promotion_code_for_customer(fresh)
        again = auth.get_by_id(cid)
        linked = bool((again.get("stripe_referral_promotion_code_id") or "").strip())
        ref_coupon = (getattr(Config, "STRIPE_REFERRAL_COUPON_ID", None) or "").strip()
        ref_secret = (getattr(Config, "STRIPE_SECRET_KEY", None) or "").strip()
        configured = bool(ref_coupon and ref_secret)
        return jsonify(
            {
                "ok": True,
                "linked": linked,
                "referral_discount_configured": configured,
            }
        )
    except Exception as e:
        print(f"[referral-stripe-sync] {e!r}")
        return jsonify({"ok": False, "linked": False, "error": "server_error"}), 500


@app.route("/api/account/billing-data", methods=["GET"])
@customer_login_required
def account_billing_data_api():
    """Hydrate subscription billing + Stripe pause state after deferred account HTML (no extra aesthetic change)."""
    customer = get_current_customer()
    if not customer:
        return jsonify({"ok": False, "error": "sign_in_required"}), 401
    try:
        caption_orders, subscription_billing = _account_fetch_merged_orders_and_stripe_billing(customer)
    except Exception as e:
        print(f"[api/account/billing-data] {e!r}")
        return jsonify({"ok": False, "error": "server_error"}), 500
    sub_orders = [o for o in caption_orders if (o.get("stripe_subscription_id") or "").strip()]
    pause_subscription_inner_html = ""
    if sub_orders:
        pause_subscription_inner_html = render_template(
            "partials/account_pause_subscription_blocks.html",
            sub_orders=sub_orders,
            subscription_billing=subscription_billing,
            captions_prices=CAPTIONS_DISPLAY_PRICES,
        )
    edit_pause_by_token = {}
    for o in caption_orders:
        t = (o.get("token") or "").strip()
        if t and (o.get("stripe_subscription_id") or "").strip():
            sp = o.get("subscription_pause") or {}
            edit_pause_by_token[t] = {
                "cancel_at_period_end": bool(sp.get("cancel_at_period_end")),
                "cancelled_now": bool(sp.get("cancelled_now")),
                "ends_at": sp.get("ends_at"),
            }
    return jsonify(
        {
            "ok": True,
            "pause_subscription_inner_html": pause_subscription_inner_html,
            "edit_pause_by_token": edit_pause_by_token,
        }
    )


@app.route('/account/pause')
def account_pause_legacy_redirect():
    """Old URL — Manage subscription lives at /account/subscription. Preserve query string (e.g. get_pack_sooner)."""
    target = url_for('account_page', section='subscription')
    if request.query_string:
        sep = '&' if '?' in target else '?'
        target = target + sep + request.query_string.decode('utf-8')
    return redirect(target, code=301)


@app.route('/account')
@app.route('/account/<section>')
@customer_login_required
def account_page(section=None):
    """Account dashboard: one section per page. Section in {information, history, edit-form, subscription, refer, prepare-pack-sooner}."""
    if not get_current_customer():
        return redirect(url_for('customer_login_page'))
    if section is None or section not in _ACCOUNT_SECTIONS:
        section = "information"
    ctx = _account_context(section=section)
    if not ctx:
        return redirect(url_for('customer_login_page'))
    # Upgrade section only for one-off customers; redirect others to edit-form
    if section == "upgrade" and not ctx.get("subscribe_options"):
        section = "edit-form"
    ctx["current_section"] = section
    ctx["upgrade_url_base_token"] = (request.args.get("base") or "").strip()
    if section == "prepare-pack-sooner":
        prep, prep_err = _prepare_pack_sooner_hub_context(get_current_customer() or {})
        ctx["prepare_pack_sooner"] = prep
        ctx["prepare_pack_sooner_error"] = prep_err
    else:
        ctx["prepare_pack_sooner"] = None
        ctx["prepare_pack_sooner_error"] = None
    return render_template("customer_dashboard.html", **ctx)


@app.route('/dashboard')
def dashboard_redirect():
    """Redirect old dashboard URL to account."""
    return redirect(url_for('account_page'))

@app.route('/form')
def lead_form_redirect():
    """Lead form removed - redirect to home."""
    return redirect(url_for('index'))

@app.route('/webhook-test')
def webhook_test():
    """Test page for webhook integrations"""
    return render_template('webhook.html')

@app.route('/activate')
def activate_page():
    """DFD shelved — redirect to Captions."""
    return redirect(url_for('captions_page'))


@app.route('/activate-success')
def activate_success_page():
    """DFD shelved — redirect to Captions."""
    return redirect(url_for('captions_page'))


@app.route('/front-desk-setup')
def front_desk_setup_page():
    """DFD shelved — redirect to Captions."""
    return redirect(url_for('captions_page'))


@app.route('/front-desk-setup-done')
def front_desk_setup_done_page():
    """DFD shelved — redirect to Captions."""
    return redirect(url_for('captions_page'))


@app.route("/oauth-config-check")
def oauth_config_check_page():
    """Plain HTML: shows whether Google OAuth env is visible to the server (for Railway debugging)."""
    google_ok = Config.oauth_google_configured()
    redirect_line = ""
    if google_ok:
        ru = google_oauth_redirect_uri()
        redirect_line = (
            "<h2 style='font-size:1.1rem;margin:1.5rem 0 0.5rem'>Copy this into Google</h2>"
            "<p><strong>1.</strong> Select the whole line in the box below and copy it (triple-click the line, then Cmd+C or Ctrl+C).</p>"
            f"<pre style='background:#f4f4f4;padding:0.75rem 1rem;border-radius:8px;overflow:auto;font-size:0.9rem;margin:0.5rem 0 1rem'>{html.escape(ru)}</pre>"
            "<p><strong>2.</strong> In Google Cloud Console: <strong>APIs &amp; Services</strong> → <strong>Credentials</strong> → your <strong>OAuth 2.0 Client ID</strong> (Web application) → <strong>Authorized redirect URIs</strong> → <strong>+ ADD URI</strong> → paste → <strong>SAVE</strong>.</p>"
            "<p>The pasted value must match this page <strong>character for character</strong> (including <code>https</code> and <code>www</code> if shown). Wrong host = set Railway <code>BASE_URL</code> to your public URL and redeploy, then refresh this page and update Google.</p>"
        )
    body = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>OAuth config</title>"
        "<meta name='robots' content='noindex'>"
        "<style>body{font-family:system-ui,sans-serif;max-width:36rem;margin:2rem auto;padding:0 1rem;line-height:1.5}"
        "code{background:#f0f0f0;padding:0.1rem 0.35rem;border-radius:4px;word-break:break-all}</style></head><body>"
        "<h1>Google OAuth on this server</h1>"
        f"<p><strong>Google:</strong> {'Yes &mdash; Continue with Google should appear on /login after a hard refresh.' if google_ok else 'No &mdash; set <code>GOOGLE_OAUTH_CLIENT_ID</code> and <code>GOOGLE_OAUTH_CLIENT_SECRET</code> on this Railway service, then redeploy.'}</p>"
        f"{redirect_line}"
        "<p>JSON: <code>GET /api/auth/oauth/status</code> (includes <code>redirect_uri</code> when configured).</p>"
        "<p><a href='/login'>Log in</a> · <a href='/'>Home</a></p>"
        "</body></html>"
    )
    return body, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.errorhandler(404)
def not_found(error):
    # Prefer HTML for browser requests so visitors see a proper page
    if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'text/html':
        return render_template('404.html'), 404
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    import traceback
    traceback.print_exc()
    payload = {'error': 'Internal server error'}
    if os.environ.get('SHOW_500_DETAIL') and not Config.is_production():
        orig = getattr(error, 'original_exception', error)
        payload['detail'] = '{}: {}'.format(type(orig).__name__, str(orig)) if orig else 'Unknown'
    if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'text/html':
        return render_template('500.html'), 500
    return jsonify(payload), 500

@app.errorhandler(Exception)
def catch_all_exception(error):
    """Capture unhandled exceptions. Return HTML for browsers, JSON for API clients."""
    from werkzeug.exceptions import HTTPException
    if isinstance(error, HTTPException):
        return error.get_response()
    import traceback
    traceback.print_exc()
    payload = {'error': 'Internal server error'}
    if os.environ.get('SHOW_500_DETAIL') and not Config.is_production():
        payload['detail'] = '{}: {}'.format(type(error).__name__, str(error))
    if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'text/html':
        return render_template('500.html'), 500
    return jsonify(payload), 500

if __name__ == '__main__':
    # Validate configuration
    try:
        Config.validate()
        print("Configuration validated")
    except ValueError as e:
        print(f"Configuration warning: {e}")
    
    # Run the app
    app.run(host='0.0.0.0', port=5001, debug=Config.FLASK_DEBUG)
