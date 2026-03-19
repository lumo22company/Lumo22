"""
Main Flask application for Lumo 22 (30 Days Captions).
"""
import os
import time
import json
import secrets
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, make_response, session
from flask_cors import CORS
from config import Config
from functools import wraps

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
from api.auth_routes import auth_bp, get_current_customer
from api.billing_routes import billing_bp

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)  # Enable CORS for API access

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


@app.before_request
def redirect_bare_domain_to_www():
    """Redirect lumo22.com (no www) to www.lumo22.com so Stripe success/cancel URLs land on the host that serves the app."""
    host = (request.host or "").strip().lower()
    if host == "lumo22.com":
        return redirect("https://www.lumo22.com" + (request.full_path or "/"), code=302)


@app.context_processor
def inject_asset_version():
    from datetime import datetime
    out = {'asset_version': _asset_version}
    out['today_str'] = datetime.utcnow().strftime('%d %B %Y')
    try:
        out['current_customer'] = get_current_customer()
    except Exception:
        out['current_customer'] = None
    return out

# Register blueprints
app.register_blueprint(api_bp)
app.register_blueprint(webhook_bp)
app.register_blueprint(captions_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(billing_bp)

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

        sched = BackgroundScheduler(daemon=True)
        sched.add_job(run_reminders_job, CronTrigger(hour=9, minute=0, timezone="UTC"))
        sched.start()
        print("[Captions reminder] scheduler started (daily 9am UTC)")
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
    """Return what this process is serving (template, asset_version, static file info). Hit this on Railway after deploy."""
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
    if token:
        try:
            from services.caption_order_service import CaptionOrderService
            svc = CaptionOrderService()
            order = svc.get_by_token(token)
            if order:
                if order.get("intake"):
                    existing_intake = order.get("intake") or {}
                platforms_count = max(1, int(order.get("platforms_count", 1)))
                selected_platforms = (order.get("selected_platforms") or "").strip() or ""
                stories_paid = bool(order.get("include_stories"))
                is_oneoff = not bool((order.get("stripe_subscription_id") or "").strip())
                # copy_from: only prefill when this order was explicitly upgraded from that one-off (one-off→subscription flow).
                # If account was deleted and user resubscribes, order has no upgraded_from_token so we do not prefill.
                if not existing_intake and copy_from:
                    upgraded_from = (order.get("upgraded_from_token") or "").strip()
                    if upgraded_from and upgraded_from == copy_from:
                        src_order = svc.get_by_token(copy_from)
                        if src_order:
                            src_email = (src_order.get("customer_email") or "").strip().lower()
                            cur_email = (order.get("customer_email") or "").strip().lower()
                            if src_email and cur_email and src_email == cur_email:
                                existing_intake = src_order.get("intake") or {}
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
    return_url = request.args.get("return_url", "").strip()
    is_upgrade_flow = bool(return_url and "/account/upgrade" in return_url)
    # Upgrade flow: Story Ideas selection on the upgrade page overrides the one-off's value so the form matches what they're subscribing to
    if is_upgrade_flow and token:
        upgrade_stories = request.args.get("upgrade_stories", "").strip()
        if upgrade_stories == "0":
            stories_paid = False
        elif upgrade_stories == "1":
            stories_paid = True
    # Upgrade flow: if they chose platform count/selection on the upgrade page, show that on the form (not the one-off's old values)
    upgrade_selected = (request.args.get("selected", "").strip() if is_upgrade_flow else "") or ""
    if is_upgrade_flow and token:
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
    if not prefilled_platform and selected_platforms:
        prefilled_platform = selected_platforms
    if is_upgrade_flow and upgrade_selected:
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
    # For "Primary platform" dropdown (single-platform): use first platform so it preselects
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
    r = make_response(render_template('captions_intake.html', intake_token=token, existing_intake=existing_intake, platforms_count=platforms_count, prefilled_platform=prefilled_platform, prefilled_primary=prefilled_primary, stories_paid=stories_paid, is_oneoff=is_oneoff, selected_platforms=selected_platforms, subscribe_url=subscribe_url, now=now, return_url=return_url, order_currency=order_currency, intake_add_platform_text=intake_add_platform_text, intake_add_stories_text=intake_add_stories_text, is_upgrade_flow=is_upgrade_flow))
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
    q = urlencode(params)
    api_url = f"/api/captions-checkout?{q}" if not platforms_invalid else None
    total = prices["oneoff"] + (platforms - 1) * prices["extra_oneoff"] + (prices["stories_oneoff"] if stories else 0)
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
        currency_symbol=prices["symbol"],
        platforms_invalid=platforms_invalid,
        add_stories_url=add_stories_url,
        add_platforms_url=add_platforms_url,
        back_to_captions_url=back_to_captions_url,
    )


@app.route('/captions-checkout-subscription')
def captions_checkout_subscription_page():
    """Pre-checkout page for Captions subscription: agree to T&Cs then continue to Stripe. Supports GBP, USD, EUR.
    Accepts copy_from=TOKEN to pass through to Stripe metadata for one-off → subscription flow.
    All subscription checkouts (new and upgrade from one-off) require login before payment."""
    from urllib.parse import urlencode, quote
    copy_from = (request.args.get("copy_from") or "").strip()
    if not get_current_customer():
        login_url = url_for("customer_login_page") + "?next=" + quote(request.full_path or "/captions-checkout-subscription", safe="")
        if copy_from:
            try:
                from services.caption_order_service import CaptionOrderService
                order = CaptionOrderService().get_by_token(copy_from)
                if order and (order.get("customer_email") or "").strip():
                    login_url += "&email=" + quote((order.get("customer_email") or "").strip(), safe="")
            except Exception:
                pass
        return redirect(login_url)
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
    if copy_from:
        params["copy_from"] = copy_from
    q = urlencode(params)
    api_url = f"/api/captions-checkout-subscription?{q}" if not platforms_invalid else None
    total = prices["sub"] + (platforms - 1) * prices["extra_sub"] + (prices["stories_sub"] if stories else 0)
    captions_prefill = "?" + q + "#pricing"
    back_to_captions_url = "/captions" + captions_prefill
    if not stories:
        add_stories_params = "stories=1&platforms=" + str(platforms) + "&currency=" + currency
        if selected:
            add_stories_params += "&selected=" + quote(selected)
        if copy_from:
            add_stories_params += "&copy_from=" + quote(copy_from)
        add_stories_url = "/captions?" + add_stories_params + "#pricing"
    else:
        add_stories_url = None
    add_platforms_url = ("/captions" + captions_prefill) if platforms < 4 else None
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
    return render_template(
        'captions_checkout_subscription.html',
        platforms=platforms,
        selected=selected,
        stories=stories,
        api_url=api_url,
        total_sub=total,
        currency_symbol=prices["symbol"],
        platforms_invalid=platforms_invalid,
        add_stories_url=add_stories_url,
        add_platforms_url=add_platforms_url,
        back_to_captions_url=back_to_captions_url,
        is_upgrade_from_oneoff=bool(copy_from),
        first_charge_date=first_charge_date_str,
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
                session.permanent = True
                session["customer_id"] = data["customer_id"]
                session["customer_email"] = data["email"]
                # Render the page in this response so session cookie is set here (no second request needed)
                return f(*args, **kwargs)
        if not get_current_customer():
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
    next_url = request.args.get('next', '').strip() or None
    prefilled_email = (request.args.get('email') or '').strip() or None
    return render_template('customer_signup.html', next_url=next_url, prefilled_email=prefilled_email)


@app.route('/login', methods=['GET', 'POST'])
def customer_login_page():
    """Login for Lumo 22 customers (DFD, Chat, Captions). GET shows form; POST does login and redirects."""
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = (request.form.get('password') or '').strip()
        next_url = request.form.get('next') or request.args.get('next') or '/account'
        if not email or not password:
            return render_template('customer_login.html', login_error='Please enter your email and password.', next_url=next_url)
        try:
            from services.customer_auth_service import CustomerAuthService
            svc = CustomerAuthService()
            customer = svc.get_by_email(email)
            if not customer or not svc.verify_password(customer, password):
                return render_template('customer_login.html', login_error='Invalid email or password.', next_url=next_url)
            if not customer.get('email_verified', True):
                return render_template('customer_login.html', login_error='Please verify your email before logging in. Check your inbox or request a new verification link.', needs_verification=True, verification_email=email, next_url=next_url)
            svc.update_last_login(customer['id'])
            session.permanent = True
            session['customer_id'] = str(customer['id'])
            session['customer_email'] = customer['email']
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
    next_url = request.args.get('next', '/account')
    prefilled_email = (request.args.get('email') or '').strip() or None
    return render_template('customer_login.html', next_url=next_url, prefilled_email=prefilled_email)


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
            session.permanent = True
            session['customer_id'] = str(customer['id'])
            session['customer_email'] = customer['email']
        return redirect(url_for('account_page') + '?email_changed=1', code=302)
    except Exception as e:
        import logging
        logging.exception("change_email_confirm failed: %s", e)
        return render_template('change_email_confirm.html', success=False, error="Something went wrong. Please try again or contact hello@lumo22.com.")


_ACCOUNT_SECTIONS = frozenset({"information", "history", "edit-form", "upgrade", "pause", "refer"})


def _account_context():
    """Load customer and account data for dashboard. Returns dict for template."""
    customer = get_current_customer()
    if not customer:
        return None
    email = customer.get("email", "")
    caption_orders = []
    referral_code = None
    try:
        from services.caption_order_service import CaptionOrderService
        from services.customer_auth_service import CustomerAuthService
        co_svc = CaptionOrderService()
        auth_svc = CustomerAuthService()
        caption_orders = co_svc.get_by_customer_email_including_stripe_customer(email)
        referral_code = auth_svc.ensure_referral_code(str(customer["id"]))
        try:
            from api.captions_routes import _get_subscription_pause_info
            for o in caption_orders:
                sub_id = (o.get("stripe_subscription_id") or "").strip()
                if sub_id:
                    try:
                        info = _get_subscription_pause_info(sub_id)
                        o["subscription_pause"] = info or {"paused": False, "resumes_at": None}
                    except Exception:
                        o["subscription_pause"] = {"paused": False, "resumes_at": None}
                else:
                    o["subscription_pause"] = None
        except Exception:
            for o in caption_orders:
                o["subscription_pause"] = None
    except Exception as e:
        print(f"[account] Error loading data: {e}")
        referral_code = None
    current_intake_order = None
    if caption_orders:
        sub_orders = [o for o in caption_orders if (o.get("stripe_subscription_id") or "").strip()]
        current_intake_order = sub_orders[0] if sub_orders else caption_orders[0]

    subscription_billing = _get_subscription_billing(caption_orders)

    # Upgrade options for one-off customers: one entry per one-off order so they can choose which pack to base a subscription on
    subscribe_options = []
    one_off_orders = [o for o in caption_orders if not (o.get("stripe_subscription_id") or "").strip()]
    if one_off_orders:
        from urllib.parse import urlencode
        for o in one_off_orders:
            token = (o.get("token") or "").strip()
            if not token:
                continue
            intake = o.get("intake") or {}
            business_name = (intake.get("business_name") or "").strip() or None
            platforms_count = max(1, int(o.get("platforms_count", 1)))
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
            subscribe_options.append({"url": url, "business_name": business_name})
    # Backward compatibility: single upgrade link (most recent one-off)
    subscribe_url = subscribe_options[0]["url"] if subscribe_options else None
    subscribe_business_name = subscribe_options[0]["business_name"] if subscribe_options else None

    base = (Config.BASE_URL or request.url_root or "").strip().rstrip("/")
    if base and not base.startswith("http"):
        base = "https://" + base
    return {
        "customer": customer,
        "caption_orders": caption_orders,
        "current_intake_order": current_intake_order,
        "subscription_billing": subscription_billing,
        "subscribe_options": subscribe_options,
        "subscribe_url": subscribe_url,
        "subscribe_business_name": subscribe_business_name,
        "one_off_orders": one_off_orders,
        "captions_prices": CAPTIONS_DISPLAY_PRICES,
        "base_url": base,
        "referral_code": referral_code or "",
        "referral_discount_credits": int(customer.get("referral_discount_credits") or 0),
    }


def _get_subscription_billing(caption_orders):
    """
    Build payment_methods list and per-subscription default for account page.
    Returns { "payment_methods": [{ id, brand, last4 }], "subscription_payment_methods": { sub_id: { id, brand, last4 } } }.
    """
    out = {"payment_methods": [], "subscription_payment_methods": {}}
    if not caption_orders or not getattr(Config, "STRIPE_SECRET_KEY", None):
        return out
    stripe_customer_id = None
    for o in caption_orders:
        cid = (o.get("stripe_customer_id") or "").strip()
        if cid:
            stripe_customer_id = cid
            break
    if not stripe_customer_id:
        return out
    try:
        import stripe
        stripe.api_key = Config.STRIPE_SECRET_KEY
        pm_list = stripe.PaymentMethod.list(customer=stripe_customer_id, type="card")
        for pm in (pm_list.data or []):
            card = (pm.get("card") or {})
            out["payment_methods"].append({
                "id": pm.get("id"),
                "brand": (card.get("brand") or "card").capitalize(),
                "last4": card.get("last4") or "****",
            })
        from api.stripe_utils import is_valid_stripe_subscription_id
        for o in caption_orders:
            sub_id = (o.get("stripe_subscription_id") or "").strip()
            if not sub_id or not is_valid_stripe_subscription_id(sub_id):
                continue
            try:
                sub = stripe.Subscription.retrieve(sub_id, expand=["default_payment_method"])
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
            except Exception:
                out["subscription_payment_methods"][sub_id] = None
    except Exception:
        pass
    return out


@app.route('/account')
@app.route('/account/<section>')
@customer_login_required
def account_page(section=None):
    """Account dashboard: one section per page. Section in {information, history, edit-form, pause, refer}."""
    if not get_current_customer():
        return redirect(url_for('customer_login_page'))
    if section is None or section not in _ACCOUNT_SECTIONS:
        section = "information"
    ctx = _account_context()
    if not ctx:
        return redirect(url_for('customer_login_page'))
    # Upgrade section only for one-off customers; redirect others to edit-form
    if section == "upgrade" and not ctx.get("subscribe_options"):
        section = "edit-form"
    ctx["current_section"] = section
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
    if os.environ.get('SHOW_500_DETAIL'):
        orig = getattr(error, 'original_exception', error)
        payload['detail'] = '{}: {}'.format(type(orig).__name__, str(orig)) if orig else 'Unknown'
    return jsonify(payload), 500

@app.errorhandler(Exception)
def catch_all_exception(error):
    """Capture unhandled exceptions so we return the real error message when SHOW_500_DETAIL is set."""
    from werkzeug.exceptions import HTTPException
    if isinstance(error, HTTPException):
        return error.get_response()
    import traceback
    traceback.print_exc()
    payload = {'error': 'Internal server error'}
    if os.environ.get('SHOW_500_DETAIL'):
        payload['detail'] = '{}: {}'.format(type(error).__name__, str(error))
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
