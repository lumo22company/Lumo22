#!/usr/bin/env python3
"""
Run caption generation + delivery (same as after intake form).
Use this to see the REAL error if the delivery email never arrives.

Usage:
  python3 test_captions_delivery.py
  python3 test_captions_delivery.py your@email.com
  python3 test_captions_delivery.py your@email.com TOKEN   # use existing order by token

Uses your .env (OpenAI, SendGrid, Supabase). If it fails here, it fails on Railway too.
"""
import sys
from dotenv import load_dotenv
load_dotenv()

def main():
    email = (sys.argv[1] if len(sys.argv) > 1 else "test@example.com").strip()
    token_arg = (sys.argv[2] if len(sys.argv) > 2 else "").strip()

    from config import Config
    from services.caption_order_service import CaptionOrderService
    from services.caption_generator import CaptionGenerator
    from services.notifications import NotificationService

    if not Config.OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY not set in .env")
        sys.exit(1)
    if not Config.SENDGRID_API_KEY:
        print("ERROR: SENDGRID_API_KEY not set in .env")
        sys.exit(1)
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        print("ERROR: Supabase not configured (SUPABASE_URL, SUPABASE_KEY)")
        sys.exit(1)

    order_service = CaptionOrderService()

    if token_arg:
        order = order_service.get_by_token(token_arg)
        if not order:
            print(f"ERROR: No order found for token {token_arg[:8]}...")
            sys.exit(1)
        if not order.get("intake"):
            print("ERROR: Order has no intake. Submit the intake form first, then run again with this token.")
            sys.exit(1)
        order_id = order["id"]
        intake = order["intake"]
        customer_email = (order.get("customer_email") or "").strip() or email
        print(f"Using existing order {order_id}, email {customer_email}")
    else:
        print(f"Creating test order and intake for {email} ...")
        order = order_service.create_order(customer_email=email, stripe_session_id=None)
        order_id = order["id"]
        intake = {
            "business_type": "Consultancy",
            "offer_one_line": "We help founders get clarity on strategy.",
            "audience": "Founders and small business owners",
            "audience_cares": "Getting unstuck and making decisions",
            "voice_words": "direct, calm, practical",
            "voice_avoid": "hype",
            "platform": "LinkedIn",
            "platform_habits": "short posts",
            "goal": "More inbound leads",
            "caption_examples": "",
        }
        order_service.save_intake(order_id, intake)
        customer_email = email
        print(f"Order created {order_id}, running generation ...")

    print("-" * 50)
    try:
        gen = CaptionGenerator()
        captions_md = gen.generate(intake)
        print("OpenAI generation OK, building PDF ...")
        from services.caption_pdf import build_caption_pdf, get_logo_path
        try:
            pdf_bytes = build_caption_pdf(captions_md, logo_path=get_logo_path())
            filename = "30_Days_Captions.pdf"
            mime_type = "application/pdf"
            file_content_bytes = pdf_bytes
            file_content = None
        except Exception as pdf_err:
            print(f"PDF build failed, falling back to .md: {pdf_err}")
            filename = "30_Days_Captions.md"
            mime_type = "text/markdown"
            file_content_bytes = None
            file_content = captions_md
        print("Sending delivery email ...")
        notif = NotificationService()
        ok, send_err = notif.send_email_with_attachment(
            customer_email,
            "Your 30 Days of Social Media Captions",
            "Hi,\n\nYour 30 Days of Social Media Captions are ready. The document is attached.\n\nLumo 22",
            filename=filename,
            file_content=file_content,
            file_content_bytes=file_content_bytes,
            mime_type=mime_type,
        )
        if ok:
            print("-" * 50)
            print("SUCCESS. Check inbox (and spam) for:", customer_email)
        else:
            print("-" * 50)
            print("FAILED:", send_err or "SendGrid returned False.")
            sys.exit(1)
    except Exception as e:
        print("-" * 50)
        print("FAILED. This is the error (fix this on Railway too):")
        print()
        print(f"  {type(e).__name__}: {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
