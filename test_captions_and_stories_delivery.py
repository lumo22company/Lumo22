#!/usr/bin/env python3
"""
Test that captions AND stories PDFs are generated and delivered for a new order.

Creates a test order with include_stories, runs the full generation + delivery flow
(same as production after intake submit), and reports success/failure.

Usage:
  python3 test_captions_and_stories_delivery.py
  python3 test_captions_and_stories_delivery.py your@email.com

Uses .env (AI, SendGrid, Supabase). Sends real email with both PDF attachments.
"""
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


def main():
    email = (sys.argv[1] if len(sys.argv) > 1 else "test@example.com").strip()

    from config import Config
    from services.caption_order_service import CaptionOrderService
    from services.caption_generator import CaptionGenerator
    from services.caption_pdf import build_caption_pdf, build_stories_pdf, get_logo_path
    from services.notifications import NotificationService

    provider = (getattr(Config, "AI_PROVIDER", None) or "openai").strip().lower()
    if provider == "anthropic":
        if not Config.ANTHROPIC_API_KEY:
            print("ERROR: ANTHROPIC_API_KEY not set (AI_PROVIDER=anthropic)")
            sys.exit(1)
    else:
        if not Config.OPENAI_API_KEY:
            print("ERROR: OPENAI_API_KEY not set in .env")
            sys.exit(1)
    if not Config.SENDGRID_API_KEY:
        print("ERROR: SENDGRID_API_KEY not set in .env")
        sys.exit(1)
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        print("ERROR: Supabase not configured (SUPABASE_URL, SUPABASE_KEY)")
        sys.exit(1)

    print(f"Creating test order with captions + stories for {email} ...")
    order_service = CaptionOrderService()
    order = order_service.create_order(customer_email=email, stripe_session_id=None)
    order_id = order["id"]

    intake = {
        "business_name": "Test Delivery Co",
        "business_type": "Consultancy",
        "offer_one_line": "We help founders get clarity on strategy.",
        "audience": "Founders and small business owners",
        "audience_cares": "Getting unstuck and making decisions",
        "voice_words": "direct, calm, practical",
        "voice_avoid": "hype",
        "platform": "Instagram & Facebook",
        "platform_habits": "short posts",
        "goal": "More inbound leads",
        "caption_examples": "",
        "include_stories": True,
        "align_stories_to_captions": False,
    }
    order_service.update(order_id, {"include_stories": True})
    order_service.save_intake(order_id, intake)

    print(f"Order {order_id} created. Generating captions + stories (this may take 1–3 min) ...")
    print("-" * 50)

    try:
        gen = CaptionGenerator()
        pack_start_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        captions_md = gen.generate(intake, pack_start_date=pack_start_date)
        print("AI generation OK")

        logo_path = get_logo_path()

        print("Building captions PDF ...")
        try:
            captions_pdf = build_caption_pdf(captions_md, logo_path=logo_path, pack_start_date=pack_start_date)
        except Exception as e:
            print(f"FAILED: Captions PDF build error: {e}")
            sys.exit(1)
        print("  Captions PDF OK")

        print("Building stories PDF ...")
        stories_pdf = build_stories_pdf(captions_md, logo_path=logo_path, pack_start_date=pack_start_date)
        if not stories_pdf:
            print("  FAILED: No stories in markdown (check platform has Instagram & Facebook)")
            sys.exit(1)
        print("  Stories PDF OK")

        extra_attachments = [
            {
                "filename": "30_Days_Story_Ideas.pdf",
                "content": stories_pdf,
                "mime_type": "application/pdf",
            }
        ]

        subject = "Your 30 Days of Social Media Captions"
        body = (
            "Hi,\n\nYour 30 Days of Social Media Captions and 30 Days of Story Ideas are ready. "
            "Both documents are attached.\n\n"
            "Copy each caption and story idea as you need them, or edit to fit.\n\n"
            "Lumo 22\n"
        )

        print("Sending delivery email with both PDFs ...")
        notif = NotificationService()
        ok, send_err = notif.send_email_with_attachment(
            email,
            subject,
            body,
            filename="30_Days_Captions.pdf",
            file_content=None,
            file_content_bytes=captions_pdf,
            mime_type="application/pdf",
            extra_attachments=extra_attachments,
        )

        if ok:
            print("-" * 50)
            print("SUCCESS. Check inbox (and spam) for:", email)
            print("  - 30_Days_Captions.pdf")
            print("  - 30_Days_Story_Ideas.pdf")
        else:
            print("-" * 50)
            print("FAILED:", send_err or "SendGrid returned False.")
            sys.exit(1)

    except Exception as e:
        print("-" * 50)
        print("FAILED:")
        print(f"  {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
