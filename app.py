"""
Main Flask application for AI-powered lead capture and booking system.
"""
import os
import time
import json
import secrets
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, make_response
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
from api.routes import api_bp, init_services
from api.webhooks import webhook_bp
from api.outreach_routes import outreach_bp, init_outreach_services
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

@app.context_processor
def inject_asset_version():
    out = {'asset_version': _asset_version}
    try:
        out['current_customer'] = get_current_customer()
    except Exception:
        out['current_customer'] = None
    return out

# Register blueprints
app.register_blueprint(api_bp)
app.register_blueprint(webhook_bp)
app.register_blueprint(outreach_bp)
app.register_blueprint(captions_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(billing_bp)

# Captions pre-pack reminder: run daily at 9am UTC (no separate cron service needed)
def _start_captions_reminder_scheduler():
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
    return render_template('landing.html')

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
    return render_template(
        'captions.html',
        captions_payment_link=Config.CAPTIONS_PAYMENT_LINK,
        use_checkout_redirect=use_checkout_redirect,
        captions_subscription_available=subscription_available,
        supports_multi_platform=supports_multi_platform,
        stories_addon_available=stories_addon_available,
        checkout_error=checkout_error,
        currencies_available=currencies_available,
        captions_prices=CAPTIONS_DISPLAY_PRICES,
    )

@app.route('/captions-intake')
def captions_intake_page():
    """Intake form for 30 Days Captions (sent to client after payment). Token in ?t= links form to order."""
    from datetime import datetime
    token = request.args.get('t', '').strip()
    existing_intake = {}
    platforms_count = 1
    selected_platforms = ""
    stories_paid = False
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
        except Exception:
            pass
    # Prefill platform from order (chosen at checkout) when they haven't saved intake yet
    prefilled_platform = (existing_intake.get("platform") or "").strip() if existing_intake else ""
    if not prefilled_platform and selected_platforms:
        prefilled_platform = selected_platforms
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
    now = datetime.utcnow()
    r = make_response(render_template('captions_intake.html', intake_token=token, existing_intake=existing_intake, platforms_count=platforms_count, prefilled_platform=prefilled_platform, stories_paid=stories_paid, now=now))
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
    from urllib.parse import urlencode
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
    q = urlencode(params)
    api_url = f"/api/captions-checkout?{q}" if not platforms_invalid else None
    total = prices["oneoff"] + (platforms - 1) * prices["extra_oneoff"] + (prices["stories_oneoff"] if stories else 0)
    return render_template(
        'captions_checkout.html',
        platforms=platforms,
        selected=selected,
        stories=stories,
        api_url=api_url,
        total_oneoff=total,
        currency_symbol=prices["symbol"],
        platforms_invalid=platforms_invalid,
    )


@app.route('/captions-checkout-subscription')
def captions_checkout_subscription_page():
    """Pre-checkout page for Captions subscription: agree to T&Cs then continue to Stripe. Supports GBP, USD, EUR."""
    from urllib.parse import urlencode
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
    q = urlencode(params)
    api_url = f"/api/captions-checkout-subscription?{q}" if not platforms_invalid else None
    total = prices["sub"] + (platforms - 1) * prices["extra_sub"] + (prices["stories_sub"] if stories else 0)
    return render_template(
        'captions_checkout_subscription.html',
        platforms=platforms,
        selected=selected,
        stories=stories,
        api_url=api_url,
        total_sub=total,
        currency_symbol=prices["symbol"],
        platforms_invalid=platforms_invalid,
    )

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
    """Digital Front Desk shelved — show coming-soon page; code kept for existing links."""
    return render_template('dfd_shelved.html')


@app.route('/book')
def booking_page():
    """Redirect to Captions (DFD shelved)."""
    return redirect(url_for('captions_page'))


@app.route('/book-demo')
def booking_demo_page():
    """Demo booking page to test Smart Scheduling: slot picker, duration, Group appointments together."""
    return render_template('booking.html')


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
                session["customer_id"] = data["customer_id"]
                session["customer_email"] = data["email"]
                # Render the page in this response so session cookie is set here (no second request needed)
                return f(*args, **kwargs)
        if not get_current_customer():
            return redirect(url_for('customer_login_page') + '?next=' + request.url)
        return f(*args, **kwargs)
    return decorated


@app.route('/signup')
def customer_signup_page():
    """Signup for Lumo 22 customers (DFD, Chat, Captions)."""
    return render_template('customer_signup.html')


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
            svc.update_last_login(customer['id'])
            session['customer_id'] = str(customer['id'])
            session['customer_email'] = customer['email']
            # One-time token so account page can set session even if cookie from this response does not persist
            login_token = _create_login_token(customer['id'], customer['email'])
            account_url = url_for('account_page') + '?login_token=' + login_token
            return render_template('login_success.html', next_url=account_url)
        except Exception:
            return render_template('customer_login.html', login_error='Something went wrong. Please try again.', next_url=next_url)
    return render_template('customer_login.html')


@app.route('/send-login-link', methods=['POST'])
def send_login_link():
    """Send a one-time login link by email. Works even when password/cookie login fails."""
    email = (request.form.get('email') or request.get_json(silent=True) or {}).get('email') or ''
    email = email.strip().lower()
    if not email or '@' not in email:
        return jsonify({"ok": False, "error": "Valid email required"}), 400
    try:
        from services.customer_auth_service import CustomerAuthService
        from services.notifications import NotificationService
        svc = CustomerAuthService()
        customer = svc.get_by_email(email)
        if not customer:
            return jsonify({"ok": True, "message": "If an account exists, we've sent a login link to that email."}), 200
        base = (getattr(Config, 'BASE_URL', None) or request.url_root or '').strip().rstrip('/')
        if not base.startswith('http'):
            base = 'https://' + base if base else request.url_root
        login_token = _create_login_token(customer['id'], customer['email'])
        account_url = base.rstrip('/') + '/account?login_token=' + login_token
        notif = NotificationService()
        subject = "Your Lumo 22 login link"
        body = "Click the link below to open your account (link works once, expires in 2 minutes):\n\n" + account_url + "\n\n— Lumo 22"
        sent = notif.send_email(email, subject, body)
        if not sent:
            return jsonify({"ok": False, "error": "Could not send email. Try again later."}), 503
        return jsonify({"ok": True, "message": "Check your email for the login link."}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": "Something went wrong. Try again."}), 500


@app.route('/forgot-password')
def forgot_password_page():
    """Forgot password: enter email, receive reset link."""
    return render_template('forgot_password.html')


@app.route('/reset-password')
def reset_password_page():
    """Reset password: token from email, set new password."""
    token = request.args.get('token', '').strip()
    return render_template('reset_password.html', token=token)


@app.route('/account')
@customer_login_required
def account_page():
    """Unified customer dashboard: DFD, Chat, Captions. Requires login."""
    customer = get_current_customer()
    if not customer:
        return redirect(url_for('customer_login_page'))
    email = customer.get('email', '')
    setups = []
    caption_orders = []
    referral_code = None
    try:
        from services.front_desk_setup_service import FrontDeskSetupService
        from services.caption_order_service import CaptionOrderService
        from services.customer_auth_service import CustomerAuthService
        fd_svc = FrontDeskSetupService()
        co_svc = CaptionOrderService()
        auth_svc = CustomerAuthService()
        setups = fd_svc.get_by_customer_email(email)
        caption_orders = co_svc.get_by_customer_email(email)
        referral_code = auth_svc.ensure_referral_code(str(customer["id"]))
        # Enrich caption orders with subscription pause status (for subscription orders)
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
    base = (Config.BASE_URL or request.url_root or "").strip().rstrip("/")
    if base and not base.startswith("http"):
        base = "https://" + base
    return render_template('customer_dashboard.html',
        customer=customer,
        setups=setups,
        caption_orders=caption_orders,
        base_url=base,
        referral_code=referral_code or "",
    )


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

@app.route('/outreach')
def outreach_dashboard():
    """Outreach dashboard for managing prospects"""
    return render_template('outreach_dashboard.html')


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
    """DFD shelved — redirect to shelved page (setup form no longer active)."""
    return redirect(url_for('digital_front_desk_page'))


@app.route('/front-desk-setup-done')
def front_desk_setup_done_page():
    """One-click 'Mark as connected' — link from the setup email to you. Marks the customer's setup connected and shows confirmation."""
    from services.front_desk_setup_service import FrontDeskSetupService
    done_token = request.args.get("t", "").strip()
    if not done_token:
        return render_template('front_desk_setup_done.html', error='Missing link'), 400
    try:
        svc = FrontDeskSetupService()
        setup = svc.get_by_done_token(done_token)
        if not setup:
            return render_template('front_desk_setup_done.html', error='Invalid or expired link'), 404
        if setup.get("status") != "connected":
            svc.mark_connected(setup["id"])
        return render_template('front_desk_setup_done.html')
    except Exception as e:
        return render_template('front_desk_setup_done.html', error=str(e)), 500


@app.errorhandler(404)
def not_found(error):
    # Prefer HTML for browser requests so visitors see a proper page
    if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'text/html':
        return render_template('404.html'), 404
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Initialize services
    try:
        init_services()
        init_outreach_services()
        print("Services initialized successfully")
    except Exception as e:
        print(f"Warning: Some services may not be available: {e}")
    
    # Validate configuration
    try:
        Config.validate()
        print("Configuration validated")
    except ValueError as e:
        print(f"Configuration warning: {e}")
    
    # Run the app
    app.run(host='0.0.0.0', port=5001, debug=Config.FLASK_DEBUG)
