"""
Generate a PDF from the 30 Days Captions markdown.
Matches 30_Days_Captions.pdf design: Lumo 22, title, subtitle, one-line metadata,
day sections with Platform / Caption / Hashtags inline, footer "-- n of N --".
"""
import os
import re
from io import BytesIO
from typing import Optional, List, Dict, Any, Tuple

BLACK = "#000000"
LUMO_GOLD = "#fff200"  # Accent yellow from brand (landing.css, BRAND_STYLE_GUIDE.md)


def _parse_markdown_to_structure(md: str) -> Tuple[Dict[str, str], List[Tuple[str, List[Dict[str, str]]]]]:
    cover = {
        "title": "30 Days of Social Media Captions",
        "business": "",
        "audience": "",
        "voice": "",
        "platform": "",
        "goal": "",
        "month_year": "",
    }
    days: List[Tuple[str, List[Dict[str, str]]]] = []
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    for line in lines:
        if line.strip().startswith("# "):
            cover["title"] = line.strip()[2:].strip()
            break

    for line in lines:
        s = line.strip()
        if "|" in s and not s.startswith("-"):
            parts = s.split("|", 1)
            if len(parts) == 2:
                cover["month_year"] = parts[1].strip()
            break

    in_intake = False
    seen_bullet = False
    for line in lines:
        s = line.strip()
        if "INTAKE SUMMARY" in s.upper():
            in_intake = True
            continue
        if in_intake and s.upper().strip() == "CAPTIONS":
            break
        if in_intake and s == "---" and seen_bullet:
            break
        if in_intake and s.startswith("-"):
            seen_bullet = True
            m = re.match(r"^-\s*(\w+(?:\s*\(\w+\))?)\s*:\s*(.*)$", s)
            if m:
                key = m.group(1).strip().lower().replace(" ", "_").replace("(s)", "s")
                val = m.group(2).strip()
                if key == "business":
                    cover["business"] = val
                elif key == "audience":
                    cover["audience"] = val
                elif key == "voice":
                    cover["voice"] = val
                elif key in ("platform_s", "platforms", "platform"):
                    cover["platform"] = val
                elif key == "goal":
                    cover["goal"] = val

    content = "\n".join(lines)
    day_sections = re.split(r"\n##\s+(Day\s+\d+\s*[—\-:\s][^\n]+)", content, flags=re.I)
    if len(day_sections) < 2:
        return cover, days

    i = 1
    while i + 1 < len(day_sections):
        day_heading = day_sections[i].strip()
        if not day_heading.lower().startswith("day "):
            i += 1
            continue
        body_text = day_sections[i + 1] if i + 1 < len(day_sections) else ""
        captions: List[Dict[str, str]] = []
        blocks = re.split(r"\n\s*\*\*Platform\s*:\s*\*\*", body_text, flags=re.I)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            cap: Dict[str, str] = {"platform": "", "hook": "", "body": "", "hashtags": ""}
            first_line = block.split("\n")[0].strip()
            if first_line:
                # Remove "**Platform:** " prefix when present (first block has no newline before it)
                pl = first_line
                for prefix in ("**Platform:** ", "**Platform:**", "Platform: "):
                    if pl.lower().startswith(prefix.lower()):
                        pl = pl[len(prefix):].strip()
                        break
                cap["platform"] = pl
            rest = "\n".join(block.split("\n")[1:]).strip()
            hook_m = re.search(r"\*\*(?:Suggested hook|Caption)\*\*\s*:\s*(.+?)(?=\n\n|\n\*\*|\Z)", rest, re.I | re.DOTALL)
            if hook_m:
                cap["hook"] = hook_m.group(1).strip()
            hashtag_m = re.search(r"\*\*Hashtags?:\*\*\s*([\s\S]+?)(?=\n\s*---|\n\s*\*\*|\n\s*##|\Z)", rest, re.I)
            if hashtag_m:
                cap["hashtags"] = hashtag_m.group(1).strip()
            main = re.sub(r"\*\*Hashtags?:\*\*[\s\S]*", "", rest, flags=re.I).strip()
            main = re.sub(r"\*\*(?:Suggested hook:|Caption:)\*\*\s*[^\n]*(?=\n\n|\n\*\*|\Z)", "", main, flags=re.I | re.DOTALL).strip()
            cap["body"] = _strip_separators(main)
            if cap["platform"] or cap["body"]:
                captions.append(cap)
        if day_heading and captions:
            days.append((day_heading, captions))
        i += 2

    return cover, days


def _escape(s: str) -> str:
    t = (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return t.replace("**", "")


def _remove_blank_lines(s: str) -> str:
    """Remove blank lines from text."""
    if not s:
        return s
    lines = [ln for ln in s.split("\n") if ln.strip()]
    return "\n".join(lines)


def _escape_and_breaks(s: str) -> str:
    """Escape for Paragraph and convert newlines to <br/> for line breaks."""
    return _escape(s or "").replace("\n", "<br/>")


def _strip_label(s: str, label: str, *, also: Optional[List[str]] = None) -> str:
    """Remove leading 'Label:' or '**Label:** ' from text to avoid duplication when we already show the label."""
    if not s:
        return s
    t = s.strip()
    labels_to_try = [label] + (also or [])
    for lbl in labels_to_try:
        for prefix in (f"**{lbl}** ", f"**{lbl}:** ", f"**{lbl}:**", f"**{lbl}**", f"{lbl}: "):
            if t.lower().startswith(prefix.lower()):
                t = t[len(prefix):].strip()
                break
        else:
            continue
        break  # found a match, exit outer loop
    # Then strip plain "Label: " (regex handles repeated occurrences)
    for lbl in labels_to_try:
        pat = re.compile(r"^\s*" + re.escape(lbl) + r"\s*:\s*", re.I)
        while pat.match(t):
            t = pat.sub("", t).strip()
    return t


def _strip_separators(s: str) -> str:
    """Remove --- separators and surrounding blank lines from content."""
    if not s:
        return s
    lines = s.split("\n")
    out = []
    for line in lines:
        if line.strip() == "---":
            continue
        out.append(line)
    return "\n".join(out).strip()


def _make_story_table_vertical(cover: Dict, days: List, normal_style, heading_style, tight_style, logo_path: Optional[str] = None, layout_label: Optional[str] = None) -> list:
    """Table layout A: each caption block = 3 rows (PLATFORM|value, CAPTION|value, HASHTAGS|value)."""
    from reportlab.platypus import Paragraph, Spacer, Image, Table, TableStyle, KeepTogether
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle

    story = []
    if layout_label:
        lbl = Paragraph(f'<font color="#999999" size="8">— {layout_label} —</font>', normal_style)
        story.append(lbl)
        story.append(Spacer(1, 2))
    try:
        story.extend(_build_header_flowables(cover, logo_path))
        story.append(Spacer(1, 8))
    except Exception:
        if logo_path and os.path.isfile(logo_path):
            try:
                img = Image(logo_path, width=40 * mm, height=40 * mm, hAlign="CENTER")
                story.append(img)
                story.append(Spacer(1, 6))
            except Exception:
                pass
        story.append(Paragraph("Lumo 22", normal_style))
        story.append(Paragraph(_escape(cover.get("title", "30 Days of Social Media Captions")), normal_style))
        subtitle = (cover.get("business", "") or "test") + (f" | {cover['month_year']}" if cover.get("month_year") else "")
        story.append(Paragraph(_escape(subtitle), normal_style))
        meta_parts = []
        for k, lbl in [("business", "Business"), ("audience", "Audience"), ("voice", "Voice"), ("platform", "Platform(s)"), ("goal", "Goal")]:
            if cover.get(k):
                meta_parts.append(f"{lbl}: {_escape(cover[k])}")
        if meta_parts:
            story.append(Paragraph("- " + " - ".join(meta_parts) + " -", normal_style))
        story.append(Spacer(1, 8))

    lbl = ParagraphStyle("TblLbl", parent=tight_style, fontName="Helvetica-Bold")
    day_hdr_style = ParagraphStyle("DayHdrTable", parent=heading_style, backColor=None, borderPadding=0)
    for day_heading, caption_list in days:
        day_para = Paragraph(f'<font color="#ffffff">{_escape(day_heading.upper())}</font>', day_hdr_style)
        # Day heading as separate 1-row table so KeepTogether prevents orphan at page bottom
        hdr_data = [[day_para, ""]]
        hdr_t = Table(hdr_data, colWidths=[25 * mm, 155 * mm])
        hdr_t.setStyle(TableStyle([
            ("SPAN", (0, 0), (1, 0)),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BLACK)),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cccccc")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        data = []
        for j, cap in enumerate(caption_list):
            hook_body = cap.get("body", "") or cap.get("hook", "")
            platform_val = _strip_label(cap.get("platform", ""), "Platform")
            caption_val = _remove_blank_lines(_strip_label(_strip_separators(hook_body), "Caption", also=["Suggested hook"]))
            hashtags_val = _strip_label(cap.get("hashtags", ""), "Hashtags", also=["Hashtag"])
            data.extend([
                [Paragraph("<nobr>Platform:</nobr>", lbl), Paragraph(_escape_and_breaks(platform_val), tight_style)],
                [Paragraph("<nobr>Caption:</nobr>", lbl), Paragraph(_escape_and_breaks(caption_val), tight_style)],
                [Paragraph("<nobr>Hashtags:</nobr>", lbl), Paragraph(_escape_and_breaks(hashtags_val), tight_style)],
            ])
            if j < len(caption_list) - 1:
                data.append([Spacer(1, 2), Spacer(1, 2)])
        content_t = Table(data, colWidths=[25 * mm, 155 * mm])
        content_t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cccccc")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(KeepTogether([hdr_t, content_t]))
        story.append(Spacer(1, 4))
    return story


def _parse_stories_section(md: str) -> List[Tuple[str, List[Dict[str, str]]]]:
    """Parse ## 30 Story Ideas section; returns list of (day_heading, captions) for PDF."""
    days: List[Tuple[str, List[Dict[str, str]]]] = []
    if "## 30 Story Ideas" not in md and "## 30 story ideas" not in md.lower():
        return days
    for m in re.finditer(r"\*\*Day\s+(\d+)\s*:\*\*\s*([^\n]+)", md, re.I):
        day_num = m.group(1).strip()
        prompt = m.group(2).strip()
        if not prompt:
            continue
        day_heading = f"Day {day_num} — Story"
        days.append((day_heading, [{"platform": "Story", "hook": prompt, "body": "", "hashtags": ""}]))
    return days


def _parse_stories_cover_from_md(md: str, captions_cover: Dict) -> Dict:
    """Extract business and month_year from Stories header; merge with captions cover for full metadata."""
    cover = dict(captions_cover)
    cover["title"] = "30 Days of Story Ideas"
    # Stories section may have "## 30 Story Ideas | Business | Month Year"
    for line in md.split("\n"):
        s = line.strip()
        if "## 30 Story Ideas" in s or "## 30 story ideas" in s.lower():
            if "|" in s:
                parts = [p.strip() for p in s.split("|")]
                if len(parts) >= 2:
                    cover["business"] = parts[1].strip()
                if len(parts) >= 3:
                    cover["month_year"] = parts[2].strip()
            break
    return cover


def _make_stories_doc_flowables(cover: Dict, days: List, normal_style, heading_style, tight_style, logo_path: Optional[str] = None) -> list:
    """Story Ideas PDF: same layout as captions — black day headers, content in white boxes. Each day = one idea."""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, KeepTogether
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle

    story = []
    story.extend(_build_stories_header_flowables(cover, logo_path))
    story.append(Spacer(1, 8))

    lbl = ParagraphStyle("TblLbl", parent=tight_style, fontName="Helvetica-Bold")
    day_hdr_style = ParagraphStyle("DayHdrTable", parent=heading_style, backColor=None, borderPadding=0)
    for day_heading, caption_list in days:
        day_para = Paragraph(f'<font color="#ffffff">{_escape(day_heading.upper())}</font>', day_hdr_style)
        hdr_data = [[day_para, ""]]
        hdr_t = Table(hdr_data, colWidths=[25 * mm, 155 * mm])
        hdr_t.setStyle(TableStyle([
            ("SPAN", (0, 0), (1, 0)),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BLACK)),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cccccc")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        prompt = ""
        if caption_list:
            prompt = (caption_list[0].get("hook") or caption_list[0].get("body", "") or "").strip()
        data = [
            [Paragraph("<nobr>Idea:</nobr>", lbl), Paragraph(_escape_and_breaks(prompt), tight_style)],
        ]
        content_t = Table(data, colWidths=[25 * mm, 155 * mm])
        content_t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cccccc")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(KeepTogether([hdr_t, content_t]))
        story.append(Spacer(1, 4))
    return story


def _build_stories_header_flowables(cover: Dict, logo_path: Optional[str]) -> list:
    """Stories PDF header — matches captions design: black bg, logo, gold labels, white values."""
    from reportlab.platypus import Table, TableStyle, Image, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle

    logo_path = logo_path or get_logo_path()
    banner_title_style = ParagraphStyle("BannerTitle", fontName=_get_heading_font(), fontSize=28, leading=32, textColor=colors.HexColor("#ffffff"))
    meta_font = _get_metadata_font()
    month_style = ParagraphStyle("HdrMonth", fontName=meta_font, fontSize=10, leading=11, textColor=colors.HexColor(LUMO_GOLD))
    lbl_style = ParagraphStyle("HdrLbl", fontName=meta_font, fontSize=9, leading=10, textColor=colors.HexColor(LUMO_GOLD))
    val_style = ParagraphStyle("HdrVal", fontName=meta_font, fontSize=9, leading=10, textColor=colors.HexColor("#ffffff"))

    logo_cell = Image(logo_path, width=40 * mm, height=40 * mm) if logo_path and os.path.isfile(logo_path) else Paragraph("", val_style)
    tbl_data = [
        [logo_cell, Paragraph('<font color="#ffffff">30 DAYS OF STORY IDEAS</font>', banner_title_style), Paragraph("", val_style)],
        [Paragraph("", val_style), Paragraph((cover.get("month_year") or "").strip().upper().replace(" ", "\u00A0"), month_style), Paragraph("", val_style)],
        [Paragraph("", val_style), Paragraph("Business:", lbl_style), Paragraph(_escape(cover.get("business", "") or ""), val_style)],
        [Paragraph("", val_style), Paragraph("Audience:", lbl_style), Paragraph(_escape(cover.get("audience", "") or ""), val_style)],
        [Paragraph("", val_style), Paragraph("Voice:", lbl_style), Paragraph(_escape(cover.get("voice", "") or ""), val_style)],
        [Paragraph("", val_style), Paragraph("Platform(s):", lbl_style), Paragraph(_escape(cover.get("platform", "") or "Instagram & Facebook"), val_style)],
        [Paragraph("", val_style), Paragraph("Goal:", lbl_style), Paragraph(_escape(cover.get("goal", "") or ""), val_style)],
    ]
    col_widths = [45 * mm, 28 * mm, 107 * mm]
    tbl = Table(tbl_data, colWidths=col_widths)
    tbl_style = [
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BLACK)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 8),
        ("LEFTPADDING", (1, 0), (1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -2), 2),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("SPAN", (0, 0), (0, -1)),
        ("SPAN", (1, 0), (2, 0)),
        ("SPAN", (1, 1), (2, 1)),
        ("LEFTPADDING", (0, 0), (0, -1), 8),
        ("LEFTPADDING", (1, 0), (1, -1), 4),
        ("LEFTPADDING", (2, 0), (2, -1), 0),
        ("RIGHTPADDING", (1, 2), (1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
    ]
    tbl.setStyle(TableStyle(tbl_style))
    return [tbl]


def build_stories_pdf(captions_md: str, logo_path: Optional[str] = None) -> Optional[bytes]:
    """Build a separate PDF for 30 Days of Story Ideas, matching the captions design. Returns None if no stories in md."""
    stories_days = _parse_stories_section(captions_md)
    if not stories_days:
        return None
    cover, _ = _parse_markdown_to_structure(captions_md)
    cover = _parse_stories_cover_from_md(captions_md, cover)

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.enums import TA_LEFT

    buffer = BytesIO()
    margin = 15 * mm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=0,
        bottomMargin=0,
    )
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("Normal", parent=styles["Normal"], fontSize=10,
        textColor=colors.HexColor(BLACK), fontName=_get_body_font(), alignment=TA_LEFT, leading=12, spaceAfter=6)
    heading = ParagraphStyle("Heading", parent=normal, fontSize=14, fontName=_get_heading_font(), spaceBefore=10, spaceAfter=6,
        textColor=colors.HexColor("#ffffff"), backColor=colors.HexColor(BLACK), borderPadding=4)
    tight = ParagraphStyle("Tight", parent=normal, spaceAfter=1)

    logo_path = logo_path or get_logo_path()
    story_flowables = _make_stories_doc_flowables(cover, stories_days, normal, heading, tight, logo_path)
    doc.build(story_flowables)
    try:
        from pypdf import PdfReader
        n_total = len(PdfReader(buffer).pages)
    except Exception:
        n_total = 1

    buffer2 = BytesIO()
    doc2 = SimpleDocTemplate(
        buffer2,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=0,
        bottomMargin=0,
    )

    def make_footer(n_total: int):
        def _draw(canvas, doc):
            p = canvas.getPageNumber()
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#666666"))
            canvas.drawCentredString(A4[0] / 2, 10 * mm, f"-- {p} of {n_total} --")
            canvas.restoreState()
        return _draw

    story_flowables2 = _make_stories_doc_flowables(cover, stories_days, normal, heading, tight, logo_path)
    doc2.build(story_flowables2, onFirstPage=make_footer(n_total), onLaterPages=make_footer(n_total))
    return buffer2.getvalue()


def build_caption_pdf(captions_md: str, logo_path: Optional[str] = None) -> bytes:
    """Build PDF using same format as 30_Days_Social_Media_Captions_FEBRUARY_2026.pdf (table_vertical). Stories are excluded — use build_stories_pdf separately."""
    cover, days = _parse_markdown_to_structure(captions_md)
    if not days and "## Day" in captions_md:
        cover, days = _parse_legacy_to_structure(captions_md, cover)
    # Stories go in a separate PDF
    data = _cover_and_days_to_dict(cover, days)
    return build_caption_pdf_from_dict(data, logo_path=logo_path or get_logo_path())


def _cover_and_days_to_dict(cover: Dict, days: List) -> Dict[str, Any]:
    """Convert parsed (cover, days) to dict format for build_caption_pdf_from_dict."""
    days_data = []
    for day_heading, caption_list in days:
        m = re.match(r"day\s+(\d+)\s*[—\-:\s]+(.+)", day_heading.strip(), re.I)
        day_num = int(m.group(1)) if m else len(days_data) + 1
        theme = (m.group(2) if m else "").strip()
        posts = []
        for cap in caption_list:
            caption_text = (cap.get("body", "") or cap.get("hook", "")).strip()
            posts.append({
                "platform": cap.get("platform", ""),
                "caption": caption_text,
                "hashtags": cap.get("hashtags", ""),
            })
        days_data.append({"day": day_num, "theme": theme, "posts": posts})
    return {
        "month_year": cover.get("month_year", ""),
        "business": cover.get("business", ""),
        "audience": cover.get("audience", ""),
        "voice": cover.get("voice", ""),
        "platforms": cover.get("platform", ""),
        "goal": cover.get("goal", ""),
        "days": days_data,
    }


def _parse_legacy_to_structure(md: str, cover: Dict) -> Tuple[Dict, List[Tuple[str, List[Dict[str, str]]]]]:
    """Fallback: parse legacy block format into (cover, days) for table_vertical layout."""
    blocks = _parse_markdown_to_blocks_legacy(md)
    days: List[Tuple[str, List[Dict[str, str]]]] = []
    current_day_heading = ""
    current_captions: List[Dict[str, str]] = []

    for i, block in enumerate(blocks):
        if block[0] == "heading":
            _, level, text = block
            if level == 1 and not cover.get("title"):
                cover["title"] = text.strip()
            elif level == 2 and text.strip().lower().startswith("day "):
                if current_day_heading and current_captions:
                    days.append((current_day_heading, current_captions))
                current_day_heading = text.strip()
                current_captions = []
        elif block[0] == "para":
            text = block[1].strip()
            if not text or ("INTAKE SUMMARY" in text.upper() and i < 10) or (text.upper() == "CAPTIONS"):
                continue
            parts = re.split(r"\*\*Platform\s*:\s*\*\*", text, flags=re.I)
            for part in parts[1:]:  # skip before first Platform
                part = part.strip()
                if not part:
                    continue
                cap: Dict[str, str] = {"platform": "", "hook": "", "body": "", "hashtags": ""}
                lines = part.split("\n")
                if lines:
                    pl = lines[0].strip()
                    for prefix in ("**Platform:** ", "**Platform:**", "Platform: "):
                        if pl.lower().startswith(prefix.lower()):
                            pl = pl[len(prefix):].strip()
                            break
                    cap["platform"] = pl
                rest = "\n".join(lines[1:]).strip()
                hook_m = re.search(r"\*\*(?:Suggested hook|Caption)\*\*\s*:\s*([\s\S]+?)(?=\n\n|\n\*\*|\Z)", rest, re.I | re.DOTALL)
                if hook_m:
                    cap["hook"] = hook_m.group(1).strip()
                hashtag_m = re.search(r"\*\*Hashtags?:\*\*\s*([\s\S]+?)(?=\n\s*---|\n\s*\*\*|\n\s*##|\Z)", rest, re.I)
                if hashtag_m:
                    cap["hashtags"] = hashtag_m.group(1).strip()
                body = re.sub(r"\*\*Hashtags?:\*\*[\s\S]*", "", rest, flags=re.I).strip()
                body = re.sub(r"\*\*(?:Suggested hook:|Caption:)\*\*\s*[^\n]*(?=\n\n|\n\*\*|\Z)", "", body, flags=re.I | re.DOTALL).strip()
                cap["body"] = _strip_separators(body)
                if cap["platform"] or cap["hook"] or cap["body"]:
                    current_captions.append(cap)
    if current_day_heading and current_captions:
        days.append((current_day_heading, current_captions))
    return cover, days


def _build_legacy_story(captions_md: str, logo_path: Optional[str], normal, heading) -> list:
    from reportlab.platypus import Paragraph, Spacer

    blocks = _parse_markdown_to_blocks_legacy(captions_md)
    story = [Paragraph("Lumo 22", normal), Spacer(1, 6)]
    for i, block in enumerate(blocks):
        if block[0] == "heading":
            _, level, text = block
            text_esc = _escape(text)
            if level == 1:
                story.append(Paragraph(text_esc, normal))
                story.append(Spacer(1, 6))
            elif level == 2:
                story.append(Paragraph(f'<font color="#ffffff">{text_esc.upper()}</font>', heading))
        elif block[0] == "para":
            text = block[1].strip()
            if not text or ("INTAKE SUMMARY" in text and i < 5) or ("CAPTIONS" in text and len(text) < 30):
                continue
            text = _escape(text)
            text = re.sub(r"\*\*([^*]+)\*\*:", lambda m: f"<b>{m.group(1).strip().title()}</b>: ", text)
            text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
            text = re.sub(r"<b>SUGGESTED HOOK</b>", "<b>Caption</b>", text, flags=re.I)
            text = text.replace("Suggested hook:", "Caption:").replace("suggested hook:", "Caption:")
            text = re.sub(r"(<b>Platform</b>\s*:\s*)Platform\s*:\s*", r"\1", text, flags=re.I)
            text = re.sub(r"(<b>Caption</b>\s*:\s*)Caption\s*:\s*", r"\1", text, flags=re.I)
            text = text.replace("\n", "<br/>")
            story.append(Paragraph(text, normal))
    return story


def _parse_markdown_to_blocks_legacy(md: str) -> list:
    blocks = []
    current = []
    for line in md.split("\n"):
        if line.strip() == "---":
            if current:
                blocks.append(("para", "\n".join(current)))
                current = []
            continue
        if line.startswith("# "):
            if current:
                blocks.append(("para", "\n".join(current)))
                current = []
            blocks.append(("heading", 1, line[2:].strip()))
            continue
        if line.startswith("## "):
            if current:
                blocks.append(("para", "\n".join(current)))
                current = []
            blocks.append(("heading", 2, line[3:].strip()))
            continue
        current.append(line)
    if current:
        blocks.append(("para", "\n".join(current)))
    return blocks


def build_caption_pdf_from_dict(data: Dict[str, Any], logo_path: Optional[str] = None) -> bytes:
    """Build PDF from dict."""
    cover = {
        "title": "30 Days of Social Media Captions",
        "business": data.get("business", ""),
        "audience": data.get("audience", ""),
        "voice": data.get("voice", ""),
        "platform": data.get("platforms", ""),
        "goal": data.get("goal", ""),
        "month_year": data.get("month_year", ""),
    }
    days = []
    for d in data.get("days", []):
        day_heading = f"Day {d.get('day', 0)} — {d.get('theme', '')}"
        posts = []
        for p in d.get("posts", []):
            caption = p.get("caption", "")
            posts.append({
                "platform": p.get("platform", ""),
                "hook": caption,
                "body": "",
                "hashtags": p.get("hashtags", ""),
            })
        days.append((day_heading, posts))
    return _build_from_structure(cover, days, logo_path or get_logo_path())


def _build_from_structure(cover: Dict, days: List, logo_path: Optional[str] = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.enums import TA_LEFT

    buffer = BytesIO()
    margin = 15 * mm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=0,
        bottomMargin=0,
    )
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("Normal", parent=styles["Normal"], fontSize=10,
        textColor=colors.HexColor(BLACK), fontName=_get_body_font(), alignment=TA_LEFT, leading=12, spaceAfter=6)
    heading = ParagraphStyle("Heading", parent=normal, fontSize=14, fontName=_get_heading_font(), spaceBefore=10, spaceAfter=6,
        textColor=colors.HexColor("#ffffff"), backColor=colors.HexColor(BLACK), borderPadding=4)
    tight = ParagraphStyle("Tight", parent=normal, spaceAfter=1)

    logo_path = logo_path or get_logo_path()
    story = _make_story_table_vertical(cover, days, normal, heading, tight, logo_path)
    doc.build(story)
    try:
        from pypdf import PdfReader
        n_total = len(PdfReader(buffer).pages)
    except Exception:
        n_total = 1

    buffer2 = BytesIO()
    doc2 = SimpleDocTemplate(
        buffer2,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=0,
        bottomMargin=0,
    )

    def make_footer(n_total: int):
        def _draw(canvas, doc):
            p = canvas.getPageNumber()
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#666666"))
            canvas.drawCentredString(A4[0] / 2, 10 * mm, f"-- {p} of {n_total} --")
            canvas.restoreState()
        return _draw

    story2 = _make_story_table_vertical(cover, days, normal, heading, tight, logo_path)
    doc2.build(story2, onFirstPage=make_footer(n_total), onLaterPages=make_footer(n_total))
    return buffer2.getvalue()


def _get_body_font() -> str:
    """Register Satoshi (Regular + Bold) if available, else Questrial, else Helvetica."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.fonts import addMapping
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        fonts_dir = os.path.join(root, "static", "fonts")
        regular = os.path.join(fonts_dir, "Satoshi-Regular.otf")
        bold = os.path.join(fonts_dir, "Satoshi-Bold.otf")
        if os.path.isfile(regular) and os.path.isfile(bold):
            pdfmetrics.registerFont(TTFont("Satoshi", regular))
            pdfmetrics.registerFont(TTFont("Satoshi-Bold", bold))
            addMapping("Satoshi", 1, 0, "Satoshi-Bold")
            return "Satoshi"
        for name, filename in [
            ("CenturyGothic", "CenturyGothic.ttf"),
            ("CenturyGothic", "century-gothic.ttf"),
            ("Questrial", "Questrial-Regular.ttf"),
        ]:
            path = os.path.join(fonts_dir, filename)
            if os.path.isfile(path):
                pdfmetrics.registerFont(TTFont(name, path))
                return name
    except Exception:
        pass
    return "Helvetica"


def _get_metadata_font() -> str:
    """Century Gothic for metadata; also checks system paths. Falls back to Questrial (similar) then Helvetica."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        fonts_dir = os.path.join(root, "static", "fonts")
        candidates = [
            (os.path.join(fonts_dir, "CenturyGothic.ttf"), "CenturyGothic"),
            (os.path.join(fonts_dir, "century-gothic.ttf"), "CenturyGothic"),
            (os.path.join(fonts_dir, "GOTHIC.TTF"), "CenturyGothic"),
            ("/Library/Fonts/Microsoft/Century Gothic.ttf", "CenturyGothic"),
            (os.path.expanduser("~/Library/Fonts/Century Gothic.ttf"), "CenturyGothic"),
            (os.path.join(fonts_dir, "Questrial-Regular.ttf"), "Questrial"),
        ]
        for path, name in candidates:
            if path and os.path.isfile(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    return name
                except Exception:
                    pass
    except Exception:
        pass
    return "Helvetica"


def _get_heading_font() -> str:
    """Register and return Bebas Neue Regular if available (matches website), else Bold, else Helvetica-Bold."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        fonts_dir = os.path.join(root, "static", "fonts")
        for name, filename in [("BebasNeue-Regular", "BebasNeue-Regular.ttf"), ("BebasNeue-Bold", "BebasNeue-Bold.ttf")]:
            font_path = os.path.join(fonts_dir, filename)
            if os.path.isfile(font_path):
                pdfmetrics.registerFont(TTFont(name, font_path))
                return name
    except Exception:
        pass
    return "Helvetica-Bold"


def get_logo_path() -> Optional[str]:
    try:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        path = os.path.join(root, "static", "images", "logo.png")
        if os.path.isfile(path):
            return path
    except Exception:
        pass
    return None


def get_caption_header_path() -> Optional[str]:
    """Path to blank Canva header image for caption PDFs."""
    try:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        path = os.path.join(root, "static", "images", "caption_header.png")
        if os.path.isfile(path):
            return path
    except Exception:
        pass
    return None


def _build_header_flowables(cover: Dict, logo_path: Optional[str]) -> list:
    """Build header: table for perfect alignment (black bg, yellow labels, white values)."""
    from reportlab.platypus import Table, TableStyle, Image, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle

    logo_path = logo_path or get_logo_path()

    banner_title_style = ParagraphStyle("BannerTitle", fontName=_get_heading_font(), fontSize=28, leading=32, textColor=colors.HexColor("#ffffff"))
    meta_font = _get_metadata_font()
    month_style = ParagraphStyle("HdrMonth", fontName=meta_font, fontSize=10, leading=11, textColor=colors.HexColor(LUMO_GOLD))
    lbl_style = ParagraphStyle("HdrLbl", fontName=meta_font, fontSize=9, leading=10, textColor=colors.HexColor(LUMO_GOLD))
    val_style = ParagraphStyle("HdrVal", fontName=meta_font, fontSize=9, leading=10, textColor=colors.HexColor("#ffffff"))

    logo_cell = Image(logo_path, width=40 * mm, height=40 * mm) if logo_path and os.path.isfile(logo_path) else Paragraph("", val_style)
    tbl_data = [
        [logo_cell, Paragraph('<font color="#ffffff">30 DAYS OF SOCIAL MEDIA CAPTIONS</font>', banner_title_style), Paragraph("", val_style)],
        [Paragraph("", val_style), Paragraph((cover.get("month_year") or "").strip().upper().replace(" ", "\u00A0"), month_style), Paragraph("", val_style)],
        [Paragraph("", val_style), Paragraph("Business:", lbl_style), Paragraph(_escape(cover.get("business", "") or ""), val_style)],
        [Paragraph("", val_style), Paragraph("Audience:", lbl_style), Paragraph(_escape(cover.get("audience", "") or ""), val_style)],
        [Paragraph("", val_style), Paragraph("Voice:", lbl_style), Paragraph(_escape(cover.get("voice", "") or ""), val_style)],
        [Paragraph("", val_style), Paragraph("Platform(s):", lbl_style), Paragraph(_escape(cover.get("platform", "") or ""), val_style)],
        [Paragraph("", val_style), Paragraph("Goal:", lbl_style), Paragraph(_escape(cover.get("goal", "") or ""), val_style)],
    ]
    col_widths = [45 * mm, 28 * mm, 107 * mm]  # narrow label col so "Business:" sits close to value
    tbl = Table(tbl_data, colWidths=col_widths)
    tbl_style = [
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BLACK)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 8),
        ("LEFTPADDING", (1, 0), (1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -2), 2),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]
    tbl_style.extend([
        ("SPAN", (0, 0), (0, -1)),
        ("SPAN", (1, 0), (2, 0)),
        ("SPAN", (1, 1), (2, 1)),
        ("LEFTPADDING", (0, 0), (0, -1), 8),
        ("LEFTPADDING", (1, 0), (1, -1), 4),
        ("LEFTPADDING", (2, 0), (2, -1), 0),
        ("RIGHTPADDING", (1, 2), (1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, 0), 12),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
    ])
    tbl.setStyle(TableStyle(tbl_style))
    return [tbl]


def _truncate(s: str, max_len: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3].rstrip() + "..."


def generate_filename(month_year: str) -> str:
    safe = (month_year or "Captions").replace(" ", "_")
    return f"30_Days_Social_Media_Captions_{safe}.pdf"
