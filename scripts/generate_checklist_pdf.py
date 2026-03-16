#!/usr/bin/env python3
"""Generate MANUAL_TEST_CHECKLIST.pdf from the checklist content."""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

OUTPUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "MANUAL_TEST_CHECKLIST.pdf")
BOX_SIZE = 12  # pt, empty checkbox size


def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=4,
        leftIndent=0,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=3,
        leftIndent=18,
        bulletIndent=0,
    )
    note_style = ParagraphStyle(
        "Note",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.gray,
        spaceAfter=4,
    )

    def checkbox_row(text):
        """One row: empty checkbox (no fill) + text."""
        tbl = Table(
            [[" ", Paragraph(text, bullet_style)]],
            colWidths=[BOX_SIZE, None],
            rowHeights=[None],
        )
        tbl.setStyle(TableStyle([
            ("BOX", (0, 0), (0, 0), 0.75, colors.black),
            ("LEFTPADDING", (0, 0), (0, 0), 2),
            ("RIGHTPADDING", (0, 0), (0, 0), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (1, 0), (1, 0), 0),
        ]))
        return tbl

    story = []

    story.append(Paragraph("Lumo 22 — Manual test checklist (print this)", title_style))
    story.append(Paragraph("Site: https://www.lumo22.com (Stripe test mode)", body_style))
    story.append(Paragraph("Date tested: _______________", body_style))
    story.append(Spacer(1, 12))

    sections = [
        ("1. Landing &amp; navigation", [
            "☐ Homepage loads; logo and main message visible",
            "☐ Captions in nav goes to captions page",
            "☐ Log in goes to login page",
            "☐ Sign up goes to signup page",
            "☐ Footer links (Terms, Privacy, Captions) work",
        ]),
        ("2. Captions product page", [
            "☐ Page shows pricing (one-off and/or subscription)",
            "☐ Currency selector works (if shown)",
            "☐ Platform count can be changed",
            "☐ Story Ideas add-on appears when relevant",
            "☐ Click through to one-off checkout works",
            "☐ Click through to subscription checkout works (if available)",
        ]),
        ("3. Checkout (one-off)", [
            "☐ Checkout page shows correct price and summary",
            "☐ Next step — read &amp; accept terms opens Terms modal",
            "☐ Scroll to bottom of terms → I have read and agree button enables",
            "☐ Cancel/close modal and try again",
            "☐ Accept terms → redirects to Stripe (test payment)",
            "☐ Complete Stripe test payment (card 4242 4242 4242 4242)",
            "☐ Redirect back to success/thank-you; confirmation email received",
            "☐ Intake form email received with link",
        ]),
        ("4. Checkout (subscription)", [
            "☐ Subscription checkout shows monthly price and summary",
            "☐ Terms modal works (same as above)",
            "☐ Complete Stripe test subscription",
            "☐ Redirect and confirmation email; intake email with link",
        ]),
        ("5. Intake form", [
            "☐ Open intake link from email (or use test link with token)",
            "☐ Form is pre-filled if editing existing order",
            "☐ Submit with required fields empty → error at top, fields highlighted in red",
            "☐ Fill all required fields and submit",
            "☐ Success message; pack email arrives (one-off) or first pack (subscription)",
        ]),
        ("6. Account (logged out)", [
            "☐ /account redirects to login",
            "☐ /account/pause redirects to login",
        ]),
        ("7. Login &amp; signup", [
            "☐ Sign up → create account → activation email",
            "☐ Click activation link → can log in",
            "☐ Log in with email/password → lands on account/dashboard",
            "☐ Log out → Account link no longer in nav",
            "☐ Forgot password → reset email → new password works",
        ]),
        ("8. Account dashboard (logged in)", [
            "☐ Account page shows 30 Days Captions section",
            "☐ Past packs listed; Download opens/downloads PDF",
            "☐ Edit form goes to intake (pre-filled)",
            "☐ Referral section: Copy link copies to clipboard (if enabled)",
        ]),
        ("9. Manage subscription (/account/pause)", [
            "(Need an active test subscription.)",
            "☐ Manage billing opens Stripe Customer Portal",
            "☐ Pause for 1 month → row shows Paused and Resume subscription",
            "☐ Resume subscription → row returns to normal",
            "☐ Add Story Ideas (if not included) → modal → confirm → row updates",
            "☐ Remove Story Ideas → terms modal → scroll to bottom → accept → row updates",
            "☐ Get your pack sooner opens first modal",
            "☐ Use current details → confirm modal with amount → Cancel (no charge)",
            "☐ Update my form → intake (pre-filled) → submit → yellow Form updated panel on return",
            "☐ On yellow panel, Confirm and get my pack → success message; pack email later",
            "☐ Cancel on panel goes back to Manage subscription",
        ]),
        ("10. Legal &amp; old products", [
            "☐ /terms — Terms &amp; Conditions, Last updated visible",
            "☐ /privacy — Privacy Policy, Last updated visible",
            "☐ /digital-front-desk → redirects to captions",
            "☐ /website-chat → redirects to captions",
            "☐ No DFD or chat links in nav or footer",
        ]),
    ]

    for title, items in sections:
        story.append(Paragraph(title, heading_style))
        for item in items:
            if item.startswith("(") and item.endswith(")"):
                story.append(Paragraph(item, note_style))
            else:
                text = item.replace("☐ ", "", 1) if item.startswith("☐ ") else item
                story.append(checkbox_row(text))
        story.append(Spacer(1, 4))

    story.append(Paragraph("Notes", heading_style))
    story.append(Paragraph("Use this space for bugs or issues:", body_style))
    story.append(Spacer(1, 24))
    story.append(Paragraph("_" * 80, note_style))
    story.append(Paragraph("_" * 80, note_style))
    story.append(Paragraph("_" * 80, note_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Lumo 22 — captions-only site. Run this on live (Stripe test mode) or staging.",
        note_style,
    ))

    doc.build(story)
    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
