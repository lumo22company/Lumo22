"""
API routes for 30 Days Captions: intake submission and (internal) generation trigger.
"""
from flask import Blueprint, request, jsonify
from config import Config

captions_bp = Blueprint("captions", __name__, url_prefix="/api")


def _run_generation_and_deliver(order_id: str):
    """Background: generate captions, save, email client. Runs outside request context."""
    from services.caption_order_service import CaptionOrderService
    from services.caption_generator import CaptionGenerator
    from services.notifications import NotificationService

    order_service = CaptionOrderService()
    row = order_service.get_by_id(order_id)
    if not row:
        return
    intake = row.get("intake") or {}
    customer_email = row.get("customer_email", "")

    order_service.set_generating(order_id)
    try:
        gen = CaptionGenerator()
        captions_md = gen.generate(intake)
        order_service.set_delivered(order_id, captions_md)
        filename = "30_Days_Captions.md"
        subject = "Your 30 Days of Social Media Captions"
        body = """Hi,

Your 30 Days of Social Media Captions are ready. The document is attached.

Copy each caption as you need it, or edit to fit. If you’d like any changes to tone or topics, reply to this email and we’ll adjust.

Lumo 22
"""
        notif = NotificationService()
        notif.send_email_with_attachment(
            customer_email,
            subject,
            body,
            filename=filename,
            file_content=captions_md,
            mime_type="text/markdown",
        )
    except Exception as e:
        print(f"Caption generation failed for order {order_id}: {e}")
        order_service.set_failed(order_id)


@captions_bp.route("/captions-intake", methods=["POST"])
def captions_intake_submit():
    """
    Submit intake for a 30 Days Captions order (identified by token).
    Saves intake and starts generation in background; returns immediately.
    """
    from services.caption_order_service import CaptionOrderService
    import threading

    data = request.get_json() or request.form
    if not data:
        return jsonify({"error": "Missing intake data"}), 400

    token = (data.get("token") or data.get("t") or "").strip()
    if not token:
        return jsonify({"error": "Missing token. Use the link from your order email."}), 400

    intake = {
        "business_type": (data.get("business_type") or "").strip(),
        "offer_one_line": (data.get("offer_one_line") or "").strip(),
        "audience": (data.get("audience") or "").strip(),
        "audience_cares": (data.get("audience_cares") or "").strip(),
        "voice_words": (data.get("voice_words") or "").strip(),
        "voice_avoid": (data.get("voice_avoid") or "").strip(),
        "platform": (data.get("platform") or "").strip(),
        "platform_habits": (data.get("platform_habits") or "").strip(),
        "goal": (data.get("goal") or "").strip(),
    }

    try:
        order_service = CaptionOrderService()
    except ValueError as e:
        return jsonify({"error": "Service unavailable"}), 503

    order = order_service.get_by_token(token)
    if not order:
        return jsonify({"error": "Invalid or expired link. Use the link from your order email."}), 404

    if order.get("status") != "awaiting_intake":
        return jsonify({"error": "This order has already been completed or is in progress."}), 400

    order_id = order["id"]
    if not order_service.save_intake(order_id, intake):
        return jsonify({"error": "Failed to save intake"}), 500

    thread = threading.Thread(target=_run_generation_and_deliver, args=(order_id,))
    thread.daemon = True
    thread.start()

    return jsonify({
        "success": True,
        "message": "Thanks. We're generating your 30 captions now. You'll receive them by email within a few minutes.",
    }), 200
