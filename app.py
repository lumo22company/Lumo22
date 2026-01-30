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
    return render_template('captions.html', captions_payment_link=Config.CAPTIONS_PAYMENT_LINK)

@app.route('/captions-intake')
def captions_intake_page():
    """Intake form for 30 Days Captions (sent to client after payment). Token in ?t= links form to order."""
    token = request.args.get('t', '').strip()
    return render_template('captions_intake.html', intake_token=token)

@app.route('/captions-thank-you')
def captions_thank_you_page():
    """Thank-you page after Stripe payment (set as redirect URL in Stripe)"""
    return render_template('captions_thank_you.html')

@app.route('/plans')
def plans_page():
    """Plans / pricing page"""
    return render_template('plans.html')

@app.route('/digital-front-desk')
def digital_front_desk_page():
    """Digital Front Desk product page: what it is + pricing, Activate now CTAs"""
    return render_template('digital_front_desk.html')

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
    """Activation page: link from AI email goes here; this page shows the Stripe/payment link"""
    return render_template('activate.html', activation_link=Config.ACTIVATION_LINK)


@app.errorhandler(404)
def not_found(error):
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
