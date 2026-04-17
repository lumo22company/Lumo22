#!/usr/bin/env python3
"""Generate ops reference PDF: caption delivery, stuck-pack banner, pack sooner."""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib import colors


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "docs", "CAPTION_DELIVERY_TROUBLESHOOTING.pdf")


def _p(text: str, style) -> Paragraph:
    # ReportLab expects XML-safe text
    t = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return Paragraph(t, style)


def build_pdf() -> None:
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "T", parent=styles["Heading1"], fontSize=15, spaceAfter=8, textColor=colors.HexColor("#111111")
    )
    h2 = ParagraphStyle(
        "H2", parent=styles["Heading2"], fontSize=11.5, spaceBefore=10, spaceAfter=5, textColor=colors.HexColor("#222222")
    )
    body = ParagraphStyle("B", parent=styles["Normal"], fontSize=9.5, leading=13, spaceAfter=5)
    mono = ParagraphStyle("M", parent=styles["Code"], fontSize=8, leading=11, fontName="Courier", textColor=colors.HexColor("#333333"))
    small = ParagraphStyle("S", parent=styles["Normal"], fontSize=8.5, leading=12, textColor=colors.HexColor("#555555"), spaceAfter=4)

    story = [
        _p("Lumo 22 — Caption delivery &amp; account warnings (operator reference)", title),
        _p(
            "Use this when customers do not receive PDFs, the account shows a stuck-pack banner, "
            "or Get my pack sooner behaves unexpectedly. Last updated for Lumo 22 stack: Railway, Supabase, Stripe, SendGrid, Anthropic/OpenAI.",
            small,
        ),
        Spacer(1, 8),
        _p("1) Clearing the warning on the account (Manage subscription)", h2),
        _p(
            "Two account panels: (A) <b>Amber</b> — status <b>generating</b> and the generation attempt started longer ago than the stale threshold (same as auto-recovery, typically 45 minutes). "
            "No customer retry button. (B) <b>Red / exhausted</b> — status <b>failed</b> and <b>delivery_failure_count</b> at or above the cap (3 automatic failures). "
            "Customer email goes out with the exhausted panel; ops alert uses <b>INTERNAL_ALERT_EMAIL</b> in Railway. "
            "Panels clear when the order becomes <b>delivered</b> after a successful run (not on a timer).",
            body,
        ),
        _p(
            "To clear: fix the underlying issue (see sections below), then run a successful delivery so status becomes <b>delivered</b> and the failure count resets.",
            body,
        ),
        _p(
            "<b>Your side (ops)</b>: ensure required Supabase columns exist (see §4). Confirm SendGrid and AI keys in Railway. "
            "Retry delivery with <b>python3 scripts/fix_and_retry_caption_delivery.py TOKEN</b> with production .env, "
            "or GET /api/captions-deliver-test?t=TOKEN&amp;secret=… (sync=1 optional).",
            body,
        ),
        _p(
            "<b>Customer side</b>: no self-serve retry on the account page. They can email hello@lumo22.com from the exhausted banner mailto. "
            "When generating is stale, recovery sends a one-time reassurance email (requires <b>database_caption_orders_generating_stuck_customer_notice.sql</b> in Supabase).",
            body,
        ),
        Spacer(1, 6),
        _p("2) Which email should the customer get?", h2),
        _p(
            "After intake or subscription delivery, the main message is the <b>delivery email</b> with PDF attachments (captions; Stories PDF if purchased). "
            "Get my pack sooner prepends payment context into that same delivery email — there is not usually a separate Stripe receipt email from Lumo for that path.",
            body,
        ),
        Spacer(1, 6),
        _p("3) Railway logs — phrases to search", h2),
        _p("[Stripe webhook] pack sooner: generation started for order", mono),
        _p("[Captions] Starting generation for order … (force_redeliver=True)", mono),
        _p("[Captions] Calling AI … / AI generation finished", mono),
        _p("[Captions] Sending delivery email to … / Delivery email sent", mono),
        _p("[Captions] Delivery email FAILED … / DELIVERY_FAILED …", mono),
        _p("[Stripe webhook] pack sooner: email does not match order — webhook aborts before generation.", mono),
        _p("[SendGrid] … (check API key, from address, activity for bounces)", small),
        Spacer(1, 6),
        _p("4) Supabase — migrations that must exist", h2),
        _p(
            "<b>delivery_archive</b> (JSONB): required before <b>set_delivered</b> can archive the previous pack when sending a new one. "
            "If missing, PostgREST error PGRST204 on column delivery_archive — generation may finish but save/email fails.",
            body,
        ),
        _p("Run in SQL Editor: <b>database_caption_orders_delivery_archive.sql</b>", mono),
        _p(
            "<b>history_hide_current</b> (boolean): optional for History behaviour; script in repo if missing.",
            body,
        ),
        _p("Run: <b>database_caption_orders_history_hide_current.sql</b>", mono),
        _p(
            "After ALTER, wait for schema cache or reload API. Free-tier <b>egress</b> over quota can cause instability — upgrade or reduce traffic if needed.",
            small,
        ),
        Spacer(1, 6),
        _p("5) Stripe — Get my pack sooner", h2),
        _p(
            "Pack sooner is driven by <b>checkout.session.completed</b> with product metadata captions_pack_sooner, not only invoice.paid. "
            "Session email should match order customer_email (or Stripe customer id must match).",
            body,
        ),
        Spacer(1, 6),
        _p("6) Account page — business name on warnings", h2),
        _p(
            "If the customer has multiple subscriptions, the stuck-pack panel shows <b>intake business_name</b> at the top when set, so they know which brand the warning refers to.",
            body,
        ),
        Spacer(1, 6),
        _p("7) Internal alert email (delivery_failure_count cap)", h2),
        _p(
            "Caption ops alerts (delivery exhausted, stuck-generating recovery, Get pack sooner webhook blocked) share the same subject prefix "
            "<b>[Lumo 22 Ops · Captions]</b> and the same body sections (WHAT HAPPENED, ORDER, …, WHERE TO LOOK) so you can search one string in the inbox. "
            "When automatic retries are exhausted, <b>one</b> email is sent; intermediate delivery failures do not email ops (Railway logs still show each attempt). "
            "Requires working SendGrid; treat the internal alert as best-effort if SendGrid fails.",
            body,
        ),
        Spacer(1, 6),
        _p("8) Quick checklist when “no email”", h2),
        _p("1. Migration applied (delivery_archive).", body),
        _p("2. Railway logs: generation finished? set_delivered / SendGrid errors?", body),
        _p("3. SendGrid activity for recipient; spam folder.", body),
        _p("4. Order status + delivery_failure_count + delivery_last_error in Supabase.", body),
        _p("5. Retry delivery after fix; confirm status → delivered.", body),
        PageBreak(),
        _p("File references (repo)", h2),
        _p("api/webhooks.py — _handle_pack_sooner_checkout_completed", mono),
        _p("api/captions_routes.py — _run_generation_and_deliver", mono),
        _p("services/caption_order_service.py — set_delivered, record_delivery_failure", mono),
        _p("services/notifications.py — send_email_with_attachment, ops alert", mono),
        _p("templates/customer_dashboard.html — stuck-pack banners", mono),
        _p("scripts/fix_and_retry_caption_delivery.py — operator retry from laptop", mono),
        Spacer(1, 12),
        _p(
            "Regenerate this PDF: <b>python3 scripts/generate_caption_delivery_troubleshoot_pdf.py</b>",
            small,
        ),
    ]

    doc.build(story)
    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
