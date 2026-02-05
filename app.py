"""
Main Flask application for AI-powered lead capture and booking system.
"""
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from config import Config
from api.routes import api_bp, init_services
from api.webhooks import webhook_bp
from api.outreach_routes import outreach_bp, init_outreach_services
from api.business_routes import business_bp
from api.captions_routes import captions_bp

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)  # Enable CORS for API access

# Register blueprints
app.register_blueprint(api_bp)
app.register_blueprint(webhook_bp)
app.register_blueprint(outreach_bp)
app.register_blueprint(business_bp)
app.register_blueprint(captions_bp)

@app.route('/')
def index():
    """Public landing page - businesses sign up here"""
    return render_template('landing.html')

@app.route('/captions')
def captions_page():
    """30 Days of Social Media Captions product page"""
    use_checkout_redirect = bool(Config.STRIPE_SECRET_KEY and Config.STRIPE_CAPTIONS_PRICE_ID)
    return render_template(
        'captions.html',
        captions_payment_link=Config.CAPTIONS_PAYMENT_LINK,
        use_checkout_redirect=use_checkout_redirect,
    )

@app.route('/captions-intake')
def captions_intake_page():
    """Intake form for 30 Days Captions (sent to client after payment). Token in ?t= links form to order."""
    token = request.args.get('t', '').strip()
    return render_template('captions_intake.html', intake_token=token)

@app.route('/captions-thank-you')
def captions_thank_you_page():
    """Thank-you page after Stripe payment (set as redirect URL in Stripe)"""
    return render_template('captions_thank_you.html')

@app.route('/captions-checkout')
def captions_checkout_page():
    """Pre-checkout page: agree to T&Cs then continue to Stripe."""
    return render_template('captions_checkout.html')

@app.route('/terms')
def terms_page():
    """Terms & Conditions."""
    return render_template('terms.html')

@app.route('/plans')
def plans_page():
    """Plans / pricing page"""
    chat_payment_link = getattr(Config, 'CHAT_PAYMENT_LINK', None)
    return render_template('plans.html', chat_payment_link=chat_payment_link)

@app.route('/digital-front-desk')
def digital_front_desk_page():
    """Digital Front Desk product page: what it is + pricing, Activate now CTAs"""
    return render_template('digital_front_desk.html')


@app.route('/website-chat')
def website_chat_page():
    """Standalone Website Chat Widget product page — chat only, no full inbox. £49/month."""
    chat_payment_link = getattr(Config, 'CHAT_PAYMENT_LINK', None)
    return render_template('website_chat.html', chat_payment_link=chat_payment_link)

@app.route('/signup')
def signup_page():
    """Business signup page"""
    return render_template('signup.html')

@app.route('/login')
def login_page():
    """Business login page"""
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """Business dashboard - requires login"""
    return render_template('business_dashboard.html')

@app.route('/form')
def lead_form():
    """Public lead capture form - requires business API key"""
    return render_template('lead_form.html')

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
    """Activation page: plan selection, T&Cs, then Stripe/payment link for Digital Front Desk."""
    return render_template('activate.html', **{
        'activation_link': Config.ACTIVATION_LINK,
        'activation_link_starter': getattr(Config, 'ACTIVATION_LINK_STARTER', None),
        'activation_link_standard': getattr(Config, 'ACTIVATION_LINK_STANDARD', None),
        'activation_link_premium': getattr(Config, 'ACTIVATION_LINK_PREMIUM', None),
    })


@app.route('/activate-success')
def activate_success_page():
    """Thank-you page after Digital Front Desk payment. Set this URL as the success URL for Front Desk Stripe Payment Links only."""
    return render_template('activate_success.html')


@app.route('/website-chat-success')
def website_chat_success_page():
    """Thank-you page after Website Chat Widget payment. Set this URL as the success URL for the chat product Payment Link only."""
    return render_template('website_chat_success.html')


@app.route('/front-desk-setup')
def front_desk_setup_page():
    """Setup form for Digital Front Desk or chat-only (product=chat&t=TOKEN from email)."""
    product = request.args.get('product', '').strip().lower()
    setup_token = request.args.get('t', '').strip()
    return render_template('front_desk_setup.html', product=product, setup_token=setup_token)


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
