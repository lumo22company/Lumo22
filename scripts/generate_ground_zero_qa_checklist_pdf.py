#!/usr/bin/env python3
"""Generate a comprehensive ground-zero QA checklist PDF."""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors


OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "GROUND_ZERO_QA_CHECKLIST.pdf",
)
BOX_SIZE = 11


def build_pdf() -> None:
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("T", parent=styles["Heading1"], fontSize=16, spaceAfter=6)
    subtitle = ParagraphStyle("ST", parent=styles["Normal"], fontSize=10, textColor=colors.gray, spaceAfter=8)
    section = ParagraphStyle("S", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    bullet = ParagraphStyle("B", parent=styles["Normal"], fontSize=9.5, leftIndent=16, spaceAfter=2, leading=12)
    note = ParagraphStyle("N", parent=styles["Normal"], fontSize=8.5, textColor=colors.gray, spaceAfter=3)

    def checkbox_row(text: str) -> Table:
        table = Table([[" ", Paragraph(text, bullet)]], colWidths=[BOX_SIZE, None])
        table.setStyle(TableStyle([
            ("BOX", (0, 0), (0, 0), 0.75, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, 0), 1),
            ("RIGHTPADDING", (0, 0), (0, 0), 4),
            ("LEFTPADDING", (1, 0), (1, 0), 0),
        ]))
        return table

    sections = [
        ("0) Environment Sanity", [
            "Supabase: caption_orders is empty (or known baseline).",
            "Supabase Auth: no leftover test users (or known list).",
            "Stripe Test mode is ON and test subscriptions are clean.",
            "Reminder cron is paused during baseline tests.",
            "Latest code is deployed on Railway.",
        ]),
        ("1) One-off Purchase Flow", [
            "Checkout one-off from /captions and confirm redirect succeeds.",
            "Order confirmation + intake email arrives.",
            "Intake link opens correct tokenized form.",
            "Submit with missing required fields to verify validation.",
            "Submit complete form and verify success state appears.",
            "Delivery email arrives with captions PDF attachment.",
            "Backup download links work and route through /api/captions-download.",
        ]),
        ("2) Caption Quality Validation", [
            "Days 1-5 are coherent and business-specific (no vague one-liners).",
            "Non-TikTok captions are substantive and readable.",
            "Hashtags stay within configured min/max.",
            "If key date/event was provided, captions and stories align to it.",
        ]),
        ("3) Stories Add-on Behavior", [
            "If Stories purchased: Stories PDF is attached and downloadable.",
            "If not purchased: no Stories attachment appears.",
            "Copy about stories timing (next pack vs instant) is accurate.",
        ]),
        ("4) Account Creation + Login", [
            "Create account from post-intake path and verify email flow.",
            "Login works and lands on account dashboard.",
            "Forgot password reset flow works end-to-end.",
        ]),
        ("5) Account Dashboard", [
            "History shows delivered packs only; downloads work.",
            "Edit form opens with prefilled answers for subscription orders.",
            "Manage billing opens Stripe portal correctly.",
            "Copy is consistent: cancellation via Manage billing and effective immediately.",
        ]),
        ("6) Subscription Flow", [
            "Subscription checkout succeeds and first pack is delivered.",
            "Manage subscription shows expected controls (pause/resume/change plan).",
            "Cancel in Stripe portal and verify app reflects canceled status.",
        ]),
        ("7) Reminder + Cancellation Safety", [
            "Manual reminders run does not send for canceled subscriptions.",
            "No 'complete your form' reminder is sent for completed/delivered orders.",
            "No duplicate reminder for same billing period.",
        ]),
        ("8) Delivery Recovery + Health", [
            "Failure metadata increments on controlled failure (count + last error).",
            "Auto-retry respects cap and then stops.",
            "captions-delivery-health endpoint reports queue/failure state.",
        ]),
        ("9) UX/Legal Consistency", [
            "404 page layout and CTA behavior are correct.",
            "Terms and Privacy pages load; Terms last-updated date is current.",
            "Terms cancellation wording matches live behavior.",
        ]),
        ("10) Launch Gate", [
            "One-off flow PASS.",
            "Subscription flow PASS.",
            "Cancel/reminder safety PASS.",
            "Backup download links PASS.",
            "No high-severity issues open.",
        ]),
    ]

    intake_sample = [
        ("Business name", "Northline Bakery"),
        ("Business type", "Product brand / E-commerce"),
        ("Offer (one line)", "Small-batch sourdough and celebration cakes for Leeds customers."),
        ("Audience", "Consumers (25-55)"),
        ("Goal", "Increase pre-orders for weekend bakes."),
        ("Key dates", "Mother's Day pre-orders open 15 April; collection 10-11 May."),
        ("Platforms", "Instagram & Facebook"),
        ("Example captions field", "Filled with a 3-sentence sample paragraph."),
    ]

    story = [
        Paragraph("Lumo 22 — Ground-Zero Comprehensive QA Checklist", title),
        Paragraph("Use for full pre-launch validation after data reset.", subtitle),
        Paragraph("Tester: ____________________    Date: ____________________", subtitle),
        Spacer(1, 6),
    ]

    for title_text, items in sections:
        story.append(Paragraph(title_text, section))
        for item in items:
            story.append(checkbox_row(item))
        story.append(Spacer(1, 2))

    story.append(Paragraph("Suggested Intake Test Data", section))
    for label, value in intake_sample:
        story.append(checkbox_row(f"{label}: {value}"))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Notes / Bugs Found", section))
    story.append(Paragraph("_" * 105, note))
    story.append(Paragraph("_" * 105, note))
    story.append(Paragraph("_" * 105, note))
    story.append(Paragraph("_" * 105, note))

    doc.build(story)
    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    build_pdf()

