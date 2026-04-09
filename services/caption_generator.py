"""
Generate 30 Days of Social Media Captions using AI (OpenAI or Anthropic Claude).
Uses the product framework: Authority, Educational, Brand Personality, Soft Promotion, Engagement.
"""
from typing import Dict, Any, Optional, Tuple, List
from config import Config
from services.ai_provider import chat_completion
from datetime import datetime, timedelta, date
import re
from difflib import SequenceMatcher

# Month names for parsing key date from intake (e.g. "30th March", "March 30")
_MONTH_NAMES = "january|february|march|april|may|june|july|august|september|october|november|december"
_MONTH_NUM = {m: i for i, m in enumerate(_MONTH_NAMES.split("|"), 1)}


def _normalize_intake_case(s: str, sentence_case: bool = False) -> str:
    """
    Normalize ALL CAPS intake text so PDFs and captions use sentence/title case, not shouting.
    Short phrases (e.g. business name, voice words) -> title case. Longer (e.g. offer, key date) -> sentence case.
    """
    if not s or not isinstance(s, str):
        return (s or "").strip()
    s = s.strip()
    if not s:
        return s
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return s
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if upper_ratio < 0.8:
        return s
    if sentence_case:
        return s[0].upper() + s[1:].lower()
    return s.title()


def _parse_key_date_from_text(text: str, pack_start_date: str) -> Optional[int]:
    """
    Parse a date from key-date text (e.g. "FREE CAKES FOR KIDS ON 30TH MARCH", "30 March", "March 30").
    Returns the 1-based day number (1–30) if the date falls within the 30-day pack, else None.
    """
    if not text or not pack_start_date:
        return None
    try:
        start = datetime.strptime(pack_start_date.strip()[:10], "%Y-%m-%d")
    except ValueError:
        return None
    text_lower = text.strip().lower()
    # Patterns: "30th march", "30 march", "march 30", "30/03", "30-03"
    day_num = None
    month_num = None
    year = start.year
    # (?:st|nd|rd|th)? day then month name
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s*(" + _MONTH_NAMES + r")(?:\s+(\d{4}))?", text_lower)
    if m:
        day_num = int(m.group(1))
        month_num = _MONTH_NUM.get(m.group(2))
        if m.group(3):
            year = int(m.group(3))
    if day_num is None or month_num is None:
        m = re.search(r"(" + _MONTH_NAMES + r")\s*(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{4}))?", text_lower)
        if m:
            month_num = _MONTH_NUM.get(m.group(1))
            day_num = int(m.group(2))
            if m.group(3):
                year = int(m.group(3))
    if day_num is None or month_num is None:
        return None
    try:
        event_date = datetime(year, month_num, day_num)
    except ValueError:
        return None
    delta = (event_date.date() - start.date()).days
    if 0 <= delta < 30:
        return delta + 1  # 1-based day number
    return None


def _calendar_date_to_pack_day(pack_start_date: str, event_date: date) -> Optional[int]:
    """Map a calendar date to 1-based pack day (1–30) or None if outside the window."""
    try:
        start = datetime.strptime(pack_start_date.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    delta = (event_date - start).days
    if 0 <= delta < 30:
        return delta + 1
    return None


def _parse_event_range_dates(text: str, pack_start_date: str) -> Optional[Tuple[date, date]]:
    """
    Parse same-month ranges like '12-13 April', '12–13 April', '12 and 13 April' (optional year).
    Returns (start_date, end_date) with start <= end, or None.
    """
    if not text or not pack_start_date:
        return None
    try:
        start = datetime.strptime(pack_start_date.strip()[:10], "%Y-%m-%d")
        default_year = start.year
    except ValueError:
        return None
    text_lower = text.strip().lower()
    # 12-13 april, 12–13 april (hyphen/en dash/em dash)
    m = re.search(
        r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s*(" + _MONTH_NAMES + r")(?:\s+(\d{4}))?",
        text_lower,
    )
    if m:
        d1, d2 = int(m.group(1)), int(m.group(2))
        month_num = _MONTH_NUM.get(m.group(3))
        year = int(m.group(4)) if m.group(4) else default_year
        if month_num:
            try:
                da = datetime(year, month_num, d1).date()
                db = datetime(year, month_num, d2).date()
                return (da, db) if da <= db else (db, da)
            except ValueError:
                pass
    # "12 and 13 april"
    m2 = re.search(
        r"(\d{1,2})\s+and\s+(\d{1,2})\s+(" + _MONTH_NAMES + r")(?:\s+(\d{4}))?",
        text_lower,
    )
    if m2:
        d1, d2 = int(m2.group(1)), int(m2.group(2))
        month_num = _MONTH_NUM.get(m2.group(3))
        year = int(m2.group(4)) if m2.group(4) else default_year
        if month_num:
            try:
                da = datetime(year, month_num, d1).date()
                db = datetime(year, month_num, d2).date()
                return (da, db) if da <= db else (db, da)
            except ValueError:
                pass
    return None


def _resolve_event_pack_bounds(
    pack_start_date: str, launch_desc_raw: str
) -> Optional[Tuple[date, date, int, int]]:
    """
    Map intake launch text to calendar bounds and pack days.
    Returns (first_cal_date, last_cal_date, first_pack_day, last_pack_day) or None.
    """
    raw = (launch_desc_raw or "").strip()
    if not raw or not pack_start_date:
        return None
    range_t = _parse_event_range_dates(raw, pack_start_date)
    if range_t:
        da, db = range_t
    else:
        kd = _parse_key_date_from_text(raw, pack_start_date)
        if kd is None:
            return None
        try:
            start = datetime.strptime(pack_start_date.strip()[:10], "%Y-%m-%d")
            da = (start + timedelta(days=kd - 1)).date()
            db = da
        except ValueError:
            return None
    sd = _calendar_date_to_pack_day(pack_start_date, da)
    ed = _calendar_date_to_pack_day(pack_start_date, db)
    if sd is None or ed is None:
        return None
    if ed < sd:
        sd, ed = ed, sd
        da, db = db, da
    return (da, db, sd, ed)


def _event_calendar_allows_weekend_phrase(da: date, db: date) -> bool:
    """
    True if "this weekend" / "next weekend" is a fair anchor for the event dates.
    Saturday–Sunday pair, or a single day on Saturday or Sunday.
    """
    if da != db:
        return da.weekday() == 5 and db.weekday() == 6 and (db - da).days == 1
    return da.weekday() in (5, 6)


def _build_event_calendar_strict_block(pack_start_date: str, launch_desc_raw: str) -> Optional[str]:
    """
    Strict EVENT_CALENDAR + COUNTDOWN_RULES for prompts when dates are parseable.
    Handles single-day (from _parse_key_date_from_text) or multi-day ranges (12–13 April).
    """
    bounds = _resolve_event_pack_bounds(pack_start_date, launch_desc_raw)
    if not bounds:
        return None
    da, db, sd, ed = bounds
    lines: List[str] = [
        "EVENT_CALENDAR (strict — captions AND Story Ideas must match; do not invent weekdays or different dates):",
        f"- First event calendar day: **{da.strftime('%a %d %b %Y')}** → Pack Day **{sd}**.",
    ]
    if db != da:
        lines.append(f"- Last event calendar day in this window: **{db.strftime('%a %d %b %Y')}** → Pack Day **{ed}**.")
    lines.append("")
    lines.append("PHASING for this event:")
    if sd > 1:
        lines.append(f"- Pack Days **1**–**{sd - 1}**: pre-event (teasers, anticipation, countdowns only).")
    lines.append(
        f"- Pack Days **{sd}**–**{ed}**: event is ON (live, ongoing, or spanning these dates) — not “tomorrow” or “in 48 hours” for this same event."
    )
    if ed < 30:
        lines.append(f"- Pack Days **{ed + 1}**–**30**: post-event (thank-you, replay, what’s next).")
    w_first = da.strftime("%A")
    w_last = db.strftime("%A")
    if db != da:
        pre_clause = (
            f"On **pre-event** days (Pack Days **1**–**{sd - 1}**), when you name which days the event happens, use **only** "
            f"**{w_first}** and **{w_last}** (or neutral wording: “the dates above”, the month/day from KEY_DATE_EVENTS) — "
            "do **not** say “Saturday and Sunday”, “this weekend” in a way that implies Sat–Sun, or any other weekday pair that contradicts DATE_CONTEXT."
            if sd > 1
            else "The event starts on Pack Day 1; do not describe the event dates using weekdays that contradict DATE_CONTEXT."
        )
        wk_lock = (
            f"WEEKDAY_LOCK — The event runs **{w_first} {da.day}** → **{w_last} {db.day}** ({da.strftime('%b')} / same month). "
            + pre_clause
        )
    else:
        wk_lock = (
            f"WEEKDAY_LOCK — The event is on **{w_first} {da.strftime('%d %b %Y')}**. "
            f"Pre-event copy must not name a different weekday for the event (e.g. do not say “Monday launch” if the event is on **{w_first}** per DATE_CONTEXT)."
        )
    if _event_calendar_allows_weekend_phrase(da, db):
        if db == da:
            weekend_note = (
                f"WEEKEND_WORDING — Single-day event on **{w_first}**. "
                "“This weekend” / “next weekend” are acceptable if they match that date in DATE_CONTEXT."
            )
        else:
            weekend_note = (
                "WEEKEND_WORDING — The event is **Saturday and Sunday** (see DATE_CONTEXT). "
                "Phrases like “this weekend” / “next weekend” are acceptable as primary time anchors when they match those dates."
            )
    else:
        weekend_note = (
            "WEEKEND_WORDING — The event is **not** a Saturday–Sunday pair. "
            "Do **not** use “this weekend” or “next weekend” as the **main** hook for when the event happens—lead with the weekdays in WEEKDAY_LOCK or explicit calendar dates first. "
            "Incidental use of “weekend” is OK only if the sentence already names the real days (e.g. “Sunday and Monday …”) so it cannot be read as Sat–Sun."
        )
    lines.extend([
        "",
        wk_lock,
        "",
        weekend_note,
        "",
        "COUNTDOWN_RULES (use DATE_CONTEXT for every Pack Day):",
        f"- Do **not** say the event is “tomorrow”, “in 48 hours”, “tonight’s your last chance before Monday launch”, or similar if Pack Day **{sd}**–**{ed}** is already on or inside the event window above — those phrases are for days **before** {da.strftime('%a %d %b')}.",
        "- “48 hours until …” must refer to a moment **two calendar days before** the first event day; only use it on the Pack Day that DATE_CONTEXT shows is exactly two days before that first day — never on the first event day itself.",
        "- “Tomorrow” on Pack Day N must mean the **next calendar day** in DATE_CONTEXT (compare the Day N and Day N+1 lines — do not invent a different weekday).",
        "- Follow **WEEKEND_WORDING** above for “this weekend” / “next weekend” (allowed only when WEEKEND_WORDING says so).",
        "- Story Idea lines must follow the **same** timeline as captions (no conflicting launch days).",
    ])
    return "\n".join(lines)


def _build_key_date_events_story_block(
    start_str: str, launch_desc_raw: str, launch_desc: str
) -> str:
    """KEY_DATE_EVENTS + EVENT_CALENDAR + IMPORTANT for story prompts (same phasing as captions)."""
    if not launch_desc:
        return ""
    key_date_day = (
        _parse_key_date_from_text(launch_desc_raw or launch_desc, start_str)
        if (launch_desc_raw or launch_desc)
        else None
    )
    event_bounds = _resolve_event_pack_bounds(start_str, launch_desc_raw) if launch_desc_raw else None
    event_strict = _build_event_calendar_strict_block(start_str, launch_desc_raw) if launch_desc_raw else None
    parts = [
        "",
        "",
        "KEY_DATE_EVENTS (user included dates in description):",
        launch_desc,
        "",
        "Phase story content by the dates above: BEFORE = anticipation, teasers, countdown; ON/DURING = announce, promote; AFTER = thank-you, feedback. Do not put launch-day tone on the wrong day. Use the actual dates from DATE_CONTEXT when mentioning when events happen—do not invent different dates or weekdays.",
    ]
    if event_strict:
        parts.extend(["", event_strict])
    if event_bounds is not None:
        _da, _db, sd, ed = event_bounds
        if sd == ed:
            pre_w = (
                f"Pre-launch/anticipation stories: days **1**–**{sd - 1}**."
                if sd > 1
                else "Pre-launch: none (the event starts on Day 1)."
            )
            post_w = (
                f"Post-event stories: days **{sd + 1}**–**30**."
                if sd < 30
                else "Post-event: none (the event falls on the last pack day)."
            )
            parts.extend([
                "",
                f"IMPORTANT — The event is one calendar day: Pack Day **{sd}** ({_da.strftime('%a %d %b %Y')}). {pre_w} On-event: Day **{sd}**. {post_w} Idea and Suggested wording must match DATE_CONTEXT and COUNTDOWN_RULES (no wrong weekdays; no “Monday launch” if the event is on Saturday/Sunday per DATE_CONTEXT).",
            ])
        else:
            pre_w = (
                f"Pre-event stories: days **1**–**{sd - 1}**."
                if sd > 1
                else "Pre-event: none (the event starts on Day 1)."
            )
            post_w = (
                f"Post-event stories: days **{ed + 1}**–**30**."
                if ed < 30
                else "Post-event: none (the event ends on the last pack day)."
            )
            parts.extend([
                "",
                f"IMPORTANT — The event spans **Pack Days {sd}–{ed}** (calendar: {_da.strftime('%a %d %b')}–{_db.strftime('%a %d %b %Y')}). {pre_w} On-event: **{sd}**–**{ed}**. {post_w} Do not imply the preview is “tomorrow” or “Monday” when DATE_CONTEXT shows otherwise. Match captions’ timeline exactly.",
            ])
    elif key_date_day is not None:
        parts.extend([
            "",
            f"IMPORTANT — The client's key date above falls on Day {key_date_day}. Write pre-launch/anticipation stories for days 1 to {key_date_day - 1}, launch-day/announcement for Day {key_date_day}, and post-launch/thank-you for days {key_date_day + 1} to 30. Suggested wording must reference the correct dates (e.g. if launch is Day 7 = Fri 27 Mar, do not say \"opens in April\" on Day 7).",
        ])
    return "\n".join(parts)


def _build_date_context(pack_start_date: str) -> Optional[str]:
    """If pack_start_date is YYYY-MM-DD, return a 30-day calendar string for the prompt. Else return None."""
    s = (pack_start_date or "").strip()
    if not s:
        return None
    try:
        start = datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None
    lines = []
    for i in range(30):
        d = start + timedelta(days=i)
        lines.append(f"Day {i + 1} = {d.strftime('%a %d %b %Y')}")
    return "\n".join(lines)


def _build_date_alignment_weekend_block(pack_start_date: str) -> str:
    """
    Rules so each day's caption matches the real calendar day in DATE_CONTEXT.
    Prevents e.g. 'As we head into the final weekend' on a Sunday post.
    """
    s = (pack_start_date or "").strip()
    if not s:
        return ""
    try:
        start = datetime.strptime(s[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    first_sunday: Optional[Tuple[int, datetime]] = None
    for i in range(30):
        d = start + timedelta(days=i)
        if d.weekday() == 6:
            first_sunday = (i + 1, d)
            break
    ex = ""
    if first_sunday:
        dn, dt = first_sunday
        ex = (
            f" For example, Pack Day **{dn}** is **{dt.strftime('%A %d %b')}** — "
            "do not write that day's caption as if the weekend is still *ahead*."
        )
    return (
        "DATE_ALIGNMENT (CRITICAL — each ## Day N **Caption:** is for the calendar day listed in DATE_CONTEXT; "
        "the client's PDF shows that date beside the post, so the copy must read correctly **on that day**):"
        "\n- **Weekend / 'this weekend':** Do **not** use \"as we head into the weekend\", \"ahead of the weekend\", "
        "\"leading up to … weekend\", or \"this weekend\" as **still upcoming** when DATE_CONTEXT for **that same Day N** "
        "is **Saturday** or **Sunday** — the reader is already in the weekend. Prefer \"today\", \"this Saturday\", "
        "\"this Sunday\", or speak to guests who are here **now**."
        "\n- **Sunday:** Never open as if the weekend hasn't started (e.g. avoid \"As we head into the final weekend …\" "
        "when the post day is Sunday). You may still state opening hours (e.g. open Saturday, closed Sunday) — factual — "
        "but the **narrative time** must match the post day."
        "\n- **Monday–Friday:** Weekend-forward lines (e.g. \"this weekend\") are fine when the calendar day is before Saturday; "
        "on **Friday**, teeing up the **weekend** is natural — but if the caption promotes **this Friday’s** own class or event (same day), "
        "use **this morning / today**, not **this Friday morning** (see **SAME_POST_DAY_AS_EVENT**)."
        "\n- **Month phrases:** \"Final weekend of [month]\" must match the calendar: if the post falls **during** that weekend, "
        "do not frame it as if you are still *before* it."
        + ex
    )


def _build_deadline_alignment_block(pack_start_date: str) -> str:
    """
    Rules so registration / early-bird deadlines align with the calendar day in DATE_CONTEXT.
    Prevents e.g. 'registration closes on 8 April' on a post dated 10 April (deadline already passed).
    """
    s = (pack_start_date or "").strip()
    if not s:
        return ""
    try:
        datetime.strptime(s[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return (
        "DEADLINE_AND_REGISTRATION_ALIGNMENT (CRITICAL — each **Caption:** is read **on** the calendar day "
        "for that Day N in **DATE_CONTEXT**; the PDF prints that date beside the post):\n"
        "- If you mention **registration closes**, **early-bird ends**, **deadline**, **last chance to register**, "
        "or similar, the **calendar date** of that deadline must be **on or after** the post day for that Day N "
        "when using **future / present** wording (e.g. “closes on…”, “ends…”, “register by…”).\n"
        "- If the real deadline is **before** the post day, use **past tense** or reframe: e.g. “Early-bird has closed; "
        "general registration is still open”, “You’ve missed the early rate — tickets still available”, not "
        "“closes on [earlier date]” as if it were still upcoming.\n"
        "- Do not invent a random calendar date for urgency that falls **before** the post day while sounding like a live deadline.\n"
        "- Event dates (e.g. when the summit runs) may be after the post day; only **deadline / registration / offer-end** "
        "dates must follow the rule above."
    )


def _build_weekday_hook_alignment_block() -> str:
    """
    Prevent hooks like 'Monday mornings at…' on a Wednesday post (Day N must match DATE_CONTEXT weekday).
    Factual operating hours listing Mon–Sun may still appear on any day.
    """
    return (
        "WEEKDAY_IN_HOOK_ALIGNMENT (CRITICAL — each **## Day N** post is read **on** the calendar day "
        "in **DATE_CONTEXT** for that N; the PDF prints that date beside the post):\n"
        "- For **Day N**, the weekday is **fixed** by DATE_CONTEXT (e.g. if Day 13 = Wed 15 Apr 2026, this post goes live on **Wednesday**).\n"
        "- In **Suggested hook** and **Caption:**, do **not** use scene-setting that names **another** weekday as if *this* post were that day "
        "(e.g. do not write “Monday mornings at [Business]…” when Day N is **Wednesday**). If you name a weekday in a *scene* hook, it must match "
        "DATE_CONTEXT for **this** Day N.\n"
        "- Prefer **non-weekday** scene-setting when variety is needed: “Mornings at [Business]…”, “Midweek classes…”, “Here at [Business]…”, “Today's …”.\n"
        "- **Factual operating hours** may list multiple weekdays (e.g. “Open Mon–Thu 8–5, Fri–Sat mornings”, “closed Sunday”) on **any** Day N — "
        "that is schedule copy, not pretending the post falls on Monday.\n"
        "- **Promoting a class or event on a *future* calendar day** is OK (e.g. on **Tuesday**, “This **Friday** morning we’re hosting…” so the reader knows which day). "
        "On the **same** calendar day as that event, do **not** use “this [weekday] morning” for that event — see **SAME_POST_DAY_AS_EVENT** below.\n"
        "- Hashtags: avoid **#MondayMotivation** (etc.) on a calendar day that is not that weekday; use neutral tags or day-appropriate tags "
        "(e.g. #WellnessWednesday on Wednesday)."
    )


def _build_same_post_day_as_event_block(pack_start_date: str) -> str:
    """
    When Day N in DATE_CONTEXT is the same weekday as a recurring class (e.g. Friday class on a Friday post),
    avoid 'This Friday morning…' (sounds like a future Friday). Use 'this morning', 'today', etc.
    """
    s = (pack_start_date or "").strip()
    if not s:
        return ""
    try:
        datetime.strptime(s[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return (
        "SAME_POST_DAY_AS_EVENT (CRITICAL — applies to **Caption:** and **Suggested hook**; read **Day N** in DATE_CONTEXT; "
        "valid for **every** weekday **Mon–Sun**, not only Friday):\n"
        "- If the post promotes a **session, class, opening, or offer that happens on the same calendar day as Day N** "
        "(e.g. Day 2 = Fri 10 Apr 2026 and you invite people to **that** Friday’s free class), the reader opens the feed **on that Friday**. "
        "Do **not** write **“This Friday morning…”**, **“Join us this Friday…”**, or **“We’re opening our doors this Friday morning…”** — that frames Friday as still **ahead**. "
        "Use **“This morning…”**, **“Today we’re…”**, **“Join us in a few hours…”**, **“We’re here until…”**, or **“Right now at [business]…”**.\n"
        "- **Very short Instagram & Facebook lines** (one or two lines): the rule still applies — do **not** open with **“This Friday morning…”** "
        "on a **Friday** post; use **“This morning…”** or **“Today…”** for a same-day class.\n"
        "- Same rule for **any** weekday: if Day N **is** Tuesday and the event is **that Tuesday**, do not say **“this Tuesday evening”** as if Tuesday were still coming — say **tonight**, **today**, **this evening**. "
        "**“This [weekday] morning/afternoon/evening”** is only when **Day N’s calendar day is *before* the day of the event** "
        "(e.g. Monday post → “this Wednesday evening” for Wednesday’s workshop). If Day N **is** that weekday, use **today / tonight / this morning**.\n"
        "- **Factual schedules** are fine on any day (e.g. “Classes run Friday and Saturday mornings”) — that is recurring hours, not pretending the post is another day.\n"
        "- **Hashtags** like #FridayMorning on an actual Friday post are OK; the **sentence copy** must still read as same-day."
    )


def _build_stories_posting_day_alignment_block(pack_start_date: str) -> str:
    """
    Story Ideas are printed beside DATE_CONTEXT dates; Suggested wording must read correctly on that calendar day.
    Fixes e.g. 'tomorrow morning … Friday' on a Friday post, or 'Friday morning' as upcoming on Saturday.
    """
    s = (pack_start_date or "").strip()
    if not s:
        return ""
    try:
        datetime.strptime(s[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return (
        "STORY_POSTING_DAY_ALIGNMENT (CRITICAL — each **Day N** row is for the calendar date shown in **DATE_CONTEXT** "
        "for that N; the PDF prints that date beside the story. **Suggested wording** is copy for posting **on that day**):\n"
        "- Before **tomorrow**, **today**, **this morning**, or naming a **weekday**, check **Day N** and **Day N+1** in DATE_CONTEXT. "
        "**Tomorrow** must mean only the **calendar day after** Day N — never a trick where “tomorrow” refers to the **same** "
        "weekday as Day N’s date.\n"
        "- If the story promotes an event on **the same calendar day as Day N** (e.g. Day 2 = Fri 10 Apr 2026 and the class is "
        "**that** Friday morning), use **this morning**, **today**, **this Friday**, **we’re live**, or **join us in a few hours** — "
        "**not** “tomorrow morning” for that same Friday.\n"
        "- On a **Friday** post, never write **“tomorrow is Friday”** or **“tomorrow morning … [Friday event]”** for the event that falls "
        "on that Friday — it is already Friday.\n"
        "- On **Saturday** or **Sunday**, do not describe **Friday’s** class as **Friday morning** in the **upcoming** sense; use "
        "**yesterday**, **last night**, **Friday’s session**, **replay**, or **who joined us**.\n"
        "- **Thursday** teasing **Friday** may use **tomorrow** correctly. **Teaser** vs **live**: a teaser the day **before** the event "
        "may use “tomorrow”; the **on-day** story must use **today / now / this morning** for that event.\n"
        "- **Calendar month (same rule as weekdays):** Read the **month name** on **Day N**’s line in **DATE_CONTEXT** (e.g. Fri **01 May** 2026 = already **May**). "
        "Do **not** frame that **same** calendar month as still **coming**, **approaching**, or **ahead** (e.g. “May is coming”, “as we head into May”, "
        "“[Month] is almost here” when the date is **already in that month** — including the 1st). "
        "Use **this month**, **early [Month]**, **[Month] is here**, **what’s new this month**, or tease **reveals this week** instead.\n"
        "- Keep **Idea** and **Suggested wording** consistent: do not label an Idea as same-day live content but use teaser-only time words."
    )


def _build_month_narrative_alignment_block(*, for_stories: bool = False) -> str:
    """
    When the 30-day window crosses a month boundary, copy must match each Day N's calendar month in DATE_CONTEXT.
    Captions already had this; stories used to omit it, causing e.g. 'April wrap' on Day 30 = Fri 08 May.
    """
    if for_stories:
        return (
            "MONTH_NARRATIVE_ALIGNMENT (CRITICAL): The story title may show **two months** (e.g. April – May 2026) when "
            "the 30-day window crosses a calendar month. **Ignore** treating the whole pack as a single month: for **each Day N**, "
            "**Idea** and **Suggested wording** must match the **calendar month** on that day's **DATE_CONTEXT** line — "
            "not only the first month in the title. "
            "If **Day 30 = Fri 08 May 2026**, do **not** write a Friday thank-you or “month wrap” that says **April** has been incredible, "
            "we're closing **April**, or throughout **April** — the reader's calendar day is **May**. "
            "Prefer **May**-appropriate framing (early month, what's ahead), month-neutral wrap language, or explicit **look-back** "
            "phrasing (e.g. “looking back at April”, “April was…”) so it is clear you mean the past month, not that the **current** "
            "calendar month is still April. "
            "If **Day N**’s DATE_CONTEXT date is **already in** a month (e.g. **01 May**), do **not** say that **same** month is "
            "**coming** or **approaching** (“May is coming”, “as we head into May”) — the reader is **in** that month; use **this month**, "
            "**early May**, **what’s new**, or tease **this week’s** reveal. "
            "If **Day N** is still in April per DATE_CONTEXT, April-themed framing for that day is fine."
        )
    return (
        "MONTH_NARRATIVE_ALIGNMENT (CRITICAL): The document subtitle may show **two months** (e.g. April – May 2026) when "
        "the 30-day window crosses a calendar month. **Ignore** any single-month habit: every **Caption:** for **Day N** "
        "must match the **calendar month (and date)** on that day's **DATE_CONTEXT** line — not the first month of the subtitle alone. "
        "If **Day 30 = Fri 08 May 2026**, do **not** write “as we close out April”, “April draws to a close”, or “throughout April we…” — "
        "May has already started; use May-appropriate or month-neutral wrap-up language. "
        "If **Day N** is already in **May** per DATE_CONTEXT, do **not** write “May is coming” or “as we head into May” — the reader is **in** May; "
        "use **this month**, **early May**, or **what’s new**. "
        "If **Day N** is still in April, April-themed framing for that day is fine."
    )


CAPTION_CATEGORIES = [
    "Authority / Expertise",
    "Educational / Value",
    "Brand Personality",
    "Soft Promotion",
    "Engagement",
]

# Approximate count per category over 30 days
CATEGORY_COUNTS = {
    "Authority / Expertise": 6,
    "Educational / Value": 6,
    "Brand Personality": 6,
    "Soft Promotion": 6,
    "Engagement": 6,
}


LANGUAGE_INSTRUCTIONS = {
    "English (UK)": "Use British English (UK) throughout: spelling (e.g. colour, favour, organise, centre, recognised), punctuation (single quotes for quotations where appropriate), and vocabulary (e.g. whilst, amongst, towards). Do not use American spellings or conventions.",
    "English (US)": "Use American English (US) throughout: spelling (e.g. color, favor, organize, center, recognized), punctuation (double quotes for quotations where appropriate), and vocabulary (e.g. while, among, toward). Do not use British spellings or conventions.",
    "Spanish": "Write ALL captions and content in Spanish. Use clear, professional Spanish appropriate for social media. Match the regional variety to the audience if specified (e.g. Spain vs Latin American Spanish).",
    "French": "Write ALL captions and content in French. Use clear, professional French appropriate for social media. Match the regional variety to the audience if specified (e.g. France vs Canadian French).",
    "German": "Write ALL captions and content in German. Use clear, professional German appropriate for social media. Use formal 'Sie' unless the brand voice suggests informal 'du'.",
    "Portuguese": "Write ALL captions and content in Portuguese. Prefer Brazilian Portuguese unless the audience suggests European Portuguese. Use clear, professional language appropriate for social media.",
    "Italian": "Write ALL captions and content in Italian. Use clear, professional Italian appropriate for social media. Match the regional variety to the audience if specified (e.g. Italy vs Swiss Italian).",
    "Dutch": "Write ALL captions and content in Dutch. Use clear, professional Dutch appropriate for social media. Match the regional variety to the audience if specified (e.g. Netherlands vs Belgian Dutch).",
    "Polish": "Write ALL captions and content in Polish. Use clear, professional Polish appropriate for social media. Use standard Polish spelling and conventions.",
    "Arabic": "Write ALL captions and content in Arabic. Use clear, professional Modern Standard Arabic (MSA) appropriate for social media, unless the audience suggests a dialect (e.g. Gulf, Levantine). Write right-to-left; the output will be displayed correctly.",
    "Turkish": "Write ALL captions and content in Turkish. Use clear, professional Turkish appropriate for social media. Use modern Turkish spelling (Latin script).",
    "Swedish": "Write ALL captions and content in Swedish. Use clear, professional Swedish appropriate for social media. Use standard Swedish spelling and conventions.",
}


def _stories_language_user_block(lang: str) -> str:
    """Reinforce that story body text must match caption_language (same as feed captions in the pack)."""
    return (
        f'\nLANGUAGE_MATCH (CRITICAL): The caption pack language is "{lang}". '
        "Write every Idea, every Suggested wording line, and all hashtag wording in that language only—"
        "the same language as the client's captions. The fixed English labels "
        '("Idea:", "Suggested wording:", "Story hashtags:") are required format only. '
        "Do not write story content in a different language based on audience location, business country, "
        "or intake examples unless the caption language explicitly is that language.\n"
    )


def _build_stories_system_prompt(intake: Dict[str, Any], *, aligned_with_captions: bool) -> str:
    """System prompt for story generation; mirrors caption language so stories are not written in another language."""
    lang = (intake.get("caption_language") or "English (UK)").strip()
    lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["English (UK)"])
    aligned = (
        "You align each day's story with that day's caption theme from an existing captions plan. "
        if aligned_with_captions
        else ""
    )
    return (
        "You write concise Story prompts (Idea, Suggested wording, Story hashtags). "
        f"{aligned}"
        "Calendar-day consistency: each Day N pairs with DATE_CONTEXT; never use “tomorrow” to mean the same calendar day as that row, "
        "and never treat a weekday named in the copy as still in the future when DATE_CONTEXT shows the post is already that day. "
        "**Calendar month:** **Idea** and **Suggested wording** must match the **calendar month** on that row of DATE_CONTEXT "
        "(see **MONTH_NARRATIVE_ALIGNMENT** in the user prompt)—do not frame **April** as the month you are in or closing when that day is already in **May**; "
        "and do not say that **same** month is **coming** or **approaching** when the date is **already in that month** (e.g. not “May is coming” on 1 May).\n\n"
        "Quality bar: as tailored as a premium 30-day story plan. "
        "Always respect INTAKE exactly: use only the client's real business name and offer—never fictional or example brands.\n\n"
        "Do not invent suppliers, mile distances, certifications, named product lines, or regional sourcing claims unless they appear in the intake (including Facts / constraints). "
        "Pasted **example captions** (if any) are for feed style only—do not treat their concrete details as true for this business in Story Ideas unless repeated in offer or Facts / constraints. Prefer generic wording when unsure.\n\n"
        f"{lang_instruction}\n\n"
        f'CRITICAL — Single language for all story content: caption language is "{lang}". '
        "Write every Idea, every Suggested wording line, and hashtag text in that language only. "
        'Fixed English labels ("Idea:", "Suggested wording:", "Story hashtags:") are structural; '
        f'all words after those labels must be in "{lang}", matching the captions pack. '
        "Do not switch language for story body text based on audience geography or business location."
    )


def _role_line_for_intake(intake: Dict[str, Any]) -> str:
    """Build a tailored role line so the AI is framed as an expert for this type of business."""
    business_type = (intake.get("business_type") or "").strip()
    offer = (intake.get("offer_one_line") or "").strip().lower()
    niche = "professional and founder-led brands"
    if business_type:
        # e.g. "Product brand / E-commerce" -> "product brand and e-commerce businesses"
        parts = [p.strip().lower() for p in business_type.split("/") if p.strip()]
        if len(parts) >= 2:
            niche = " and ".join(parts) + " businesses"
        elif len(parts) == 1:
            p = parts[0]
            niche = (p + "s") if not p.endswith("s") else p  # e.g. "service business" -> "service businesses"
    # If offer strongly suggests a niche, use it when it's clearer (e.g. "I make cakes" and no type)
    if offer and len(offer) < 60:
        if any(w in offer for w in ("cake", "baking", "bakery")):
            niche = "cake makers and bakeries"
        elif any(w in offer for w in ("coach", "consulting", "strategy")):
            niche = "coaches and consultants"
    return f"You are a top social media manager for {niche}. You write scroll-stopping, conversion-focused captions that fit the brand and drive engagement."


def _build_system_prompt(intake: Dict[str, Any]) -> str:
    lang = (intake.get("caption_language") or "English (UK)").strip()
    lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["English (UK)"])
    role_line = _role_line_for_intake(intake)
    vary_ig_fb_block = ""
    if _effective_vary_ig_fb_caption_length(intake):
        vary_ig_fb_block = (
            "Instagram & Facebook — caption length variety (client opted in): Across the 30 **Instagram & Facebook** captions only, deliberately vary how long each post runs—"
            "roughly a third very short (1–2 tight lines or one strong sentence with concrete detail), a third medium (about 2–4 short sentences as usual), "
            "and a third a bit more developed (still feed-appropriate, not essays). Every caption must stand alone: the reader still understands what the business offers "
            "and who it is for—no cryptic fragments. Other platforms in the intake keep their normal length rules (e.g. LinkedIn may be longer).\n\n"
        )
    return f"""{role_line} You are also a senior content strategist and conversion-focused copywriter. You write social media captions.

Quality bar: Every caption set must be as tailored and specific as a premium copywriter would deliver for this exact business—no generic filler, no wrong dates, no off-brand tone. Match the standard of a highly polished 30-day plan.

{lang_instruction}

Tone: confident, editorial, modern, premium. When the client specifies "Voice / tone to use" or "Words / style to avoid" in the intake, match those preferences—they override the default. No emojis. No buzzwords or marketing clichés. Smart, human, intelligent. Avoid hype and generic AI language.

Variety and anti-repetition: Every caption must feel fresh and distinct. Use a wide range of vocabulary—avoid reusing the same words, phrases, hooks, or openings across days. Vary sentence structures, transitions, and sign-offs. No two captions should start with the same opener (e.g. avoid "Here's the thing" or "Let's talk about" repeatedly). Rotate through different angles, examples, and approaches. If you've used a phrase in one caption, use different wording in the next.

You produce a 30-day caption plan using exactly these five categories, distributed across the month:
- Authority / Expertise (establish credibility, perspective, experience)
- Educational / Value (teach something useful, answer a real question)
- Brand Personality (process, philosophy, behind-the-scenes)
- Soft Promotion (invite a next step, mention offer, low pressure)
- Engagement (questions, prompts, conversation starters)

Engagement category (CRITICAL — intra-pack variety): The plan has **six** Engagement days. Each must use a **different conversation mechanic** — do not repeat the same question type or “origin story” angle twice in one pack. Rotate, for example: a specific scenario (“when was the last time…”), fill-in-the-blank, this-or-that / A vs B, a quick 1–10 or poll, myth vs fact, favourite ritual/prop/teacher, or “what surprised you when…”. **Forbidden:** Multiple Engagement days that all ask “what brought you to [topic]?” / “why did you start?” / “share your origin story” in the same shape. **Forbidden:** Reusing the same opener twice (e.g. “Was it a recommendation from a friend…” or “We’d love to hear your story—drop a comment”) on more than one Engagement day. If Day A asks how people discovered the practice, Day B must change the angle (obstacles, habits, class vibe, what keeps them coming back phrased differently — not a second “why did you start?”). Vary CTAs and hooks so the six days feel deliberately different.

Output format: You must respond with a single markdown document. Structure:
1. Title: "# 30 Days of Social Media Captions"
2. Subtitle: "[Business name from intake, or a brief identifier] | [Current month year]"
3. Section "---" then "INTAKE SUMMARY" then "---" then bullet lines: Business, Audience, Voice, Platform(s), Goal (from the intake).
4. Section "---" then "CAPTIONS" then "---"
5. For each day (1–30): "## Day N — [Category name only]" then for each platform (see below) repeat: "**Platform:** [exact platform label]" then "**Caption:**" then the full caption as one block—**length depends on platform** (see Instagram/Facebook and LinkedIn rules below; TikTok = 1–3 short lines)—everything the client should paste into the post, with no separate "hook line" only. If HASHTAGS_REQUESTED is true, then a blank line then "**Hashtags:** [MIN–MAX hashtags for this caption, comma-separated or space-separated]". Then "---" only after all platforms for that day are done. If HASHTAGS_REQUESTED is false, do NOT include any **Hashtags:** line.

Standalone clarity (CRITICAL): Every caption must make sense on its own in the feed. Do not write dangling one-liners that rely on unstated context. Avoid opening with bare "That's…", "This is…", or "Here's the difference…" unless the same caption immediately explains what you mean with concrete detail (what you offer, who it's for, what makes it different). Authority and Educational posts still need specifics—location, service, guest experience, or a clear insight—not a vague punchline.

CRITICAL — Completeness: Every day (1–30) must have exactly one caption block per platform. Never leave a **Caption:** or **Hashtags:** line empty. Every platform for every day must have a full, copy-paste-ready caption (length per platform rules below; TikTok = 1–3 lines). If HASHTAGS_REQUESTED is true, every caption must include a **Hashtags:** line with at least MIN and at most MAX hashtags. If you are generating only a range of days (e.g. 11–20), every day in that range must still have every platform complete. Do not output placeholder text or skip any day/platform.

Multi-platform (captions for every platform every day): When the client has more than one platform (e.g. Instagram & Facebook, LinkedIn, Pinterest), you must write one caption for EACH platform on EACH day. So for each day 1–30: first "## Day N — [Category]", then one full caption block (Platform, hook, caption, Hashtags if requested) for platform A, then the same for platform B, then platform C, etc. Each day therefore contains as many captions as there are platforms — all for that same day. "Instagram & Facebook" counts as one platform: use that label and write one caption that works for both. Rotate through the five categories across the 30 days so the mix is balanced (roughly 6 days per category). Do not duplicate the same caption across platforms; tailor each to the platform (e.g. LinkedIn more professional, TikTok shorter, Pinterest keyword-rich).

TikTok: When TikTok is one of the client's platforms, for days assigned to TikTok write shorter, punchier captions (1–3 short lines; hook in the first line; clear CTA). Use fewer hashtags and TikTok-appropriate tag style for those days.

Pinterest: When Pinterest is one of the client's platforms, for days assigned to Pinterest write search-friendly, keyword-rich descriptions (clear title and description; include relevant keywords and a clear CTA/link where appropriate).

Hashtag guidance (when HASHTAGS_REQUESTED is true): Every single caption MUST include a **Hashtags:** line. Never omit hashtags for any day or platform. Choose hashtags that support algorithm reach and discovery. Use a mix of (a) niche/specific tags relevant to the client's industry and audience, and (b) broader, high-activity tags where the content fits. Match hashtags to the caption topic and the platform for that day (e.g. LinkedIn vs Instagram vs TikTok norms). Avoid banned or spammy tags. Hashtag count per caption must fall strictly between HASHTAG_MIN and HASHTAG_MAX (inclusive).

Single platform: Write 30 distinct captions (one per day). Multiple platforms: Write 30 × [number of platforms] distinct captions — for each day, one caption per platform. Rotate through the five categories across days so the mix is balanced (roughly 6 days per category). Every caption must be tailored to the client's business, audience, voice, the platform it is for, and goal. Each caption must also be linguistically distinct: vary your vocabulary, sentence openings, and structure so the full set avoids repetition and feels varied. When a business name is provided, use it naturally where it fits (e.g. sign-offs, occasional mentions like "At [name] we...") — don't force it into every caption. No placeholder text. No "[insert X]". Match length to platform: **Instagram & Facebook** = feed-short (see above); **LinkedIn** = often 2–6 short paragraphs when appropriate; **TikTok** = 1–3 lines; **Pinterest** = keyword-rich as needed. Copy-paste ready.

Day headings (CRITICAL): Each line must be exactly `## Day N — [one of the five category names]`. Do not put calendar dates, weekdays, or "6 Apr 2026"-style text in the day heading—the client's PDF adds dates automatically; dates in the heading duplicate in the exported PDF.

Calendar-day alignment (CRITICAL): The user prompt includes **DATE_CONTEXT** (and may include **DATE_ALIGNMENT**, **SAME_POST_DAY_AS_EVENT**). Each **Caption:** for Day N must read correctly **on the calendar day** for that N. If that day is **Saturday** or **Sunday**, do **not** use "heading into the weekend", "ahead of the weekend", or "this weekend" as something still **in the future**. On **Sunday**, never imply the weekend has not started yet. **Mon–Thu** may tee up the weekend when natural. If the caption promotes a **class or offer on the same calendar day as Day N** (e.g. Friday class on a Friday post), do **not** open with **"this Friday morning"** / **"this [weekday]…"** for that same-day event — use **this morning**, **today**; reserve **"this [weekday]"** for posts **before** that weekday. **Applies to short and long copy alike** (including a two-line IG post): never **This Tuesday evening** on a Tuesday, etc. **Calendar month:** If **DATE_CONTEXT** for Day N is in **May**, do not write “closing out **April**” or “**April** draws to a close” for that day — match the **actual month** of that date line (see **MONTH_NARRATIVE_ALIGNMENT** in the user prompt). Do not frame that **same** calendar month as still **coming** when the post is **already in that month** (e.g. not “May is coming” on 1 May).

Deadlines and registration (CRITICAL): When **DATE_CONTEXT** and/or **DEADLINE_AND_REGISTRATION_ALIGNMENT** are in the user prompt, do **not** state a **registration close**, **early-bird end**, or **deadline** on a **calendar date before** that Day N’s post date while making it sound like the deadline is still **upcoming** (e.g. “closes on 8 April” on a 10 April post). Use past tense or move the deadline to on/after the post day.

Named people (CRITICAL): Do not invent specific names of employees, customers, collaborators, or fictional staff unless the intake explicitly names them. Use generic roles (e.g. "our team", "the grower", "a customer") instead.

Business relevance (CRITICAL): Every caption must be clearly about THIS business—what they actually sell or do, who they serve, and their specific product or service. Do not write generic "founder", "strategy", "building a brand", or "scaling a business" captions that could apply to any company. If the business is cakes and baking, reference cakes, baking, ingredients, orders, customers, flavours, etc. If the business is coaching, reference coaching, clients, sessions, outcomes. Match the vocabulary and examples to the business type and "What they offer" from the intake. A reader should immediately understand which industry and offer the caption is for.

Factual claims (CRITICAL): Do not state specific suppliers, mills, farms, mile distances, organic or other certifications, named product SKUs, regional labels, or sourcing stories unless they appear in the user prompt **outside pasted example captions**—e.g. **Facts / constraints**, offer line, usual topics, business context, platform habits, launch/key-date text. **Example captions** are for style, tone, pacing, and structure only: never treat their place names, numbers, product claims, sourcing, awards, or other specifics as true for this client unless the same facts appear in non-example intake fields. If a detail is not stated there, use general language (e.g. "thoughtfully sourced ingredients", "local partners", "our kitchen")—never plausible-sounding invented precision.

{vary_ig_fb_block}Launch/event phasing (when LAUNCH_EVENT / KEY_DATE_EVENTS is provided in the user prompt): If the user prompt includes **EVENT_CALENDAR**, **WEEKDAY_LOCK**, **WEEKEND_WORDING**, or **COUNTDOWN_RULES**, treat them as authoritative: multi-day windows stay “on-event” for every Pack Day in that window—do not use “tomorrow”, “48 hours”, or “Monday launch” in ways that contradict **DATE_CONTEXT**. Follow **WEEKEND_WORDING** for when “this weekend” / “next weekend” are allowed. When **WEEKDAY_LOCK** lists the weekdays (e.g. Sunday–Monday), never substitute “Saturday and Sunday” or imply Sat–Sun. Otherwise: days before launch = pre-launch; launch / event days = announcement, go-live; days after = post-launch (thank-you, feedback — NOT hype or anticipation). You MUST reflect the client's named event(s), sale(s), or launch date(s) in the **Caption:** body text on the correct days—not only in the document header or intake summary. Caption copy and Story Ideas must follow the same before / on / after timeline."""


def extract_day_categories_from_captions_md(captions_md: str) -> list:
    """Extract the category for each day (1–30) from captions markdown. Returns a list of 30 strings (category names); missing days are empty strings."""
    categories_by_day = {}
    for line in captions_md.splitlines():
        m = re.match(r"^##\s*Day\s+(\d+)\s*[—-]\s*(.+)$", line.strip())
        if not m:
            continue
        try:
            day_num = int(m.group(1))
        except ValueError:
            continue
        if 1 <= day_num <= 30:
            categories_by_day[day_num] = m.group(2).strip()
    return [categories_by_day.get(i, "") for i in range(1, 31)]


def _build_user_prompt(
    intake: Dict[str, Any],
    day_start: int = 1,
    day_end: int = 30,
    previous_pack_themes: Optional[list] = None,
    pack_start_date: Optional[str] = None,
) -> str:
    """Build user prompt. If day_start/day_end are not 1–30, generate full doc; else generate only that range.
    pack_start_date: YYYY-MM-DD so Day 1 = this date; used for date context and key-date alignment."""
    from datetime import datetime
    start_str = (pack_start_date or "").strip() or datetime.utcnow().strftime("%Y-%m-%d")
    month_year = datetime.strptime(start_str[:10], "%Y-%m-%d").strftime("%B %Y")
    include_hashtags = intake.get("include_hashtags", True)
    if isinstance(include_hashtags, str) and include_hashtags.lower() in ("false", "0", "no", "off"):
        include_hashtags = False
    hashtag_min = max(1, min(30, int(intake.get("hashtag_min") or 3)))
    hashtag_max = max(0, min(30, int(intake.get("hashtag_max") or 10)))
    if hashtag_min > hashtag_max:
        hashtag_max = hashtag_min
    platform_raw = (intake.get("platform") or "").strip()
    platform_list = [p.strip() for p in platform_raw.split(",") if p.strip()] if platform_raw else []
    if not platform_list:
        platform_list = ["Not specified"]

    range_note = ""
    if 1 <= day_start <= day_end <= 30 and (day_start != 1 or day_end != 30):
        range_note = f"\n\nGenerate ONLY days {day_start} to {day_end} (inclusive). Output only those day sections (## Day N — ... through ## Day {day_end} — ...). No title, no intake summary — just the day blocks.\n"

    # Normalize ALL CAPS intake so PDFs and captions use sentence/title case
    n = _normalize_intake_case
    business_name = n(intake.get("business_name") or "", sentence_case=False) or "Not specified"
    business_type = n(intake.get("business_type") or "", sentence_case=False)
    offer_one_line = n(intake.get("offer_one_line") or "", sentence_case=True)
    operating_hours = n(intake.get("operating_hours") or "", sentence_case=True)
    audience = n(intake.get("audience") or "", sentence_case=False) or "Not specified"
    consumer_age = n(intake.get("consumer_age_range") or "", sentence_case=False) or "Not specified"
    audience_cares = n(intake.get("audience_cares") or "", sentence_case=True)
    usual_topics = n(intake.get("usual_topics") or "", sentence_case=True)
    platform_habits = n(intake.get("platform_habits") or "", sentence_case=True) or "None"
    goal = n(intake.get("goal") or "", sentence_case=False)
    voice_words = n(intake.get("voice_words") or "", sentence_case=False)
    voice_avoid = n(intake.get("voice_avoid") or "", sentence_case=True)
    facts_guardrails = n(intake.get("facts_guardrails") or "", sentence_case=True)

    parts = [
        f"Generate the full 30-day caption document for this client. Current month/year: {month_year}.",
        f"HASHTAGS_REQUESTED: {str(include_hashtags).lower()}",
        f"HASHTAG_MIN: {hashtag_min}",
        f"HASHTAG_MAX: {hashtag_max}",
        "",
        "INTAKE (use these normalized forms in captions—do not repeat ALL CAPS):",
        f"- Business name: {business_name}",
        f"- Business type: {business_type}",
        f"- What they offer (one sentence): {offer_one_line}",
        f"- Operating hours: {operating_hours or 'Not specified'}",
        f"- Primary audience: {audience}",
        f"- Consumer age range (if applicable): {consumer_age}",
        f"- What audience cares about: {audience_cares}",
        f"- What they usually talk about (content themes): {usual_topics or 'Not specified'}",
        f"- Voice / tone to use: {voice_words or 'Not specified'}",
        f"- Words / style to avoid: {voice_avoid or 'None'}",
        f"- Platform(s): {platform_raw or 'Not specified'}",
        f"- Platform habits: {platform_habits}",
        f"- Goal for the month: {goal}",
        f"- Caption language: {intake.get('caption_language', 'English (UK)')}",
        f"- Facts / constraints (only state what is true; never invent contrary claims): {facts_guardrails or 'Not specified'}",
        "",
        "RELEVANCE: Every caption must be clearly about this business—their product/service, their audience, their offer. Do not write generic business/strategy/founder captions that could apply to any company. Ground specifics in the intake—use concrete details the client actually provided (offer, themes, examples, Facts / constraints). A reader should know which industry and offer the caption is for.",
        "",
        "Do not invent specific people's names (employees, customers, or collaborators) unless the intake explicitly names them. Use generic roles (e.g. our team, the person who packs your order) instead.",
        "",
        "FACTUAL GROUNDING: Do not invent suppliers, mills, farms, mile radii, certifications, named product lines, delivery regions, or other concrete operational claims unless they appear in intake **outside example captions** (Facts / constraints, offer, usual topics, etc.). Do not lift specifics from example captions alone—those may be inspiration from other brands. When a detail is not stated outside examples, stay general.",
        "",
        "VOICE: Match the client's voice (Voice / tone to use) and avoid their listed words or style (Words / style to avoid). When the goal is leads or inquiries, include a clear, low-pressure next step (e.g. link in bio, DM, book a call) where it fits naturally.",
        "",
        (
            "SUBSTANCE: Every caption must be clear enough that a stranger understands the offer—never a cryptic fragment with no context. For **Instagram & Facebook** this client opted into **varied lengths**: across the month mix shorter punchy posts with medium and slightly longer feed-style posts (see system prompt). Short days must still pack concrete detail—no vague fragments. "
            if _effective_vary_ig_fb_caption_length(intake)
            else "SUBSTANCE: Every caption must be clear enough that a stranger understands the offer—never a cryptic fragment with no context. For **Instagram & Facebook**: keep copy **tight** (hook first, then usually **2–4 short sentences** or a few short lines)—**not** a long essay unless Platform habits asks for longer. "
        )
        + "For **LinkedIn**: multiple sentences and depth are fine. For **Pinterest**: descriptive, keyword-aware. Days 1–2 set the tone: be specific about the business, location, or guest value.",
    ]
    if len(platform_list) > 1:
        parts.append("")
        parts.append(
            f"For EACH day (1–30), write one caption for EACH of these platforms: {', '.join(platform_list)}. "
            "So each day has " + str(len(platform_list)) + " captions — one per platform. Use **Platform:** [exact label] before each caption. "
            "'Instagram & Facebook' is one platform: one caption for both. Tailor each caption to the platform (e.g. LinkedIn tone vs TikTok short punchy vs Pinterest keyword-rich)."
        )
    elif len(platform_list) == 1 and platform_list[0] not in ("Not specified", ""):
        parts.append("")
        parts.append("Write one caption per day (30 total). Label each with **Platform:** " + platform_list[0] + ".")
    examples = (intake.get("caption_examples") or "").strip()
    if examples:
        parts.extend([
            "",
            "EXAMPLE CAPTIONS (style / tone / structure only — NOT a source of facts):",
            "These lines are for rhythm, voice, and format. Do **not** treat names, places, numbers, product claims, sourcing, certifications, or other specifics that appear **only** here as true about this business. Ground every factual claim in the rest of the intake.",
            "",
            "Pasted examples:",
            examples,
        ])

    # Launch/event: pass description (normalized case) and explicitly map key date to day number
    launch_desc_raw = (intake.get("launch_event_description") or "").strip()
    launch_desc = _normalize_intake_case(launch_desc_raw, sentence_case=True) if launch_desc_raw else ""
    key_date_day = _parse_key_date_from_text(launch_desc_raw or launch_desc, start_str) if (launch_desc_raw or launch_desc) else None
    event_bounds = _resolve_event_pack_bounds(start_str, launch_desc_raw) if launch_desc_raw else None
    event_strict = _build_event_calendar_strict_block(start_str, launch_desc_raw) if launch_desc_raw else None
    if launch_desc:
        parts.extend([
            "",
            "KEY_DATE_EVENTS (user included dates in description):",
            launch_desc,
            "",
            "Phase content by the dates above: BEFORE = anticipation, teasers; ON/DURING = announce, promote; AFTER = thank-you, feedback. Support multiple events if listed.",
        ])
        if event_strict:
            parts.extend(["", event_strict])
        if event_bounds is not None:
            _da, _db, sd, ed = event_bounds
            if sd == ed:
                pre_w = (
                    f"Pre-launch/anticipation: days **1**–**{sd - 1}**."
                    if sd > 1
                    else "Pre-launch: none (the event starts on Day 1)."
                )
                post_w = (
                    f"Post-event: days **{sd + 1}**–**30**."
                    if sd < 30
                    else "Post-event: none (the event falls on the last pack day)."
                )
                parts.extend([
                    "",
                    f"IMPORTANT — The client's event window is a single calendar day: Pack Day **{sd}** ({_da.strftime('%a %d %b %Y')}). {pre_w} On-event: Day **{sd}**. {post_w} Follow EVENT_CALENDAR and COUNTDOWN_RULES above; do not contradict DATE_CONTEXT.",
                    "",
                    "KEY_DATE_EVENTS — caption bodies: Most captions in those phases must clearly reference the client's specific event, sale, or launch inside the **Caption:** text—not only in hashtags. Do not leave KEY_DATE_EVENTS only in Story Ideas while captions stay generic.",
                ])
            else:
                pre_w = (
                    f"Pre-event: days **1**–**{sd - 1}**."
                    if sd > 1
                    else "Pre-event: none (the event starts on Day 1)."
                )
                post_w = (
                    f"Post-event: days **{ed + 1}**–**30**."
                    if ed < 30
                    else "Post-event: none (the event ends on the last pack day)."
                )
                parts.extend([
                    "",
                    f"IMPORTANT — The client's event spans **Pack Days {sd}–{ed}** (calendar: {_da.strftime('%a %d %b')}–{_db.strftime('%a %d %b %Y')}). {pre_w} On-event (live / spanning dates): **{sd}**–**{ed}**. {post_w} Do not treat only Day {sd} as “launch” and Day {ed} as after the event. Follow EVENT_CALENDAR and COUNTDOWN_RULES above.",
                    "",
                    "KEY_DATE_EVENTS — caption bodies: Most captions in those phases must clearly reference the client's specific event, sale, or launch inside the **Caption:** text—not only in hashtags. Do not leave KEY_DATE_EVENTS only in Story Ideas while captions stay generic.",
                ])
        elif key_date_day is not None:
            parts.extend([
                "",
                f"IMPORTANT — The client's key date above falls on Day {key_date_day}. Write pre-launch/anticipation content for days 1 to {key_date_day - 1}, launch-day/announcement content for Day {key_date_day}, and post-launch/thank-you content for days {key_date_day + 1} to 30. Do not put launch-day tone on the wrong day.",
                "",
                "KEY_DATE_EVENTS — caption bodies: In this day range, most captions must clearly reference the client's specific event, sale, or launch (by name or unmistakable paraphrase) inside the **Caption:** text—not only in hashtags. Pre-launch days should tee up the event; the key day must announce or mark it; post-launch days should follow with thank-you, replay, or results. Do not leave KEY_DATE_EVENTS only in Story Ideas while captions stay generic.",
            ])
        else:
            parts.extend([
                "",
                "KEY_DATE_EVENTS — caption bodies: The client listed dates or events above. Weave those specific events into **Caption:** text across the appropriate days (before / during / after as described). Captions must not ignore these events while stories mention them—keep the same timeline in both.",
            ])

    # Date context: Day 1 = pack_start_date so captions are date-aware and key date aligns
    date_context = _build_date_context(start_str)
    if date_context:
        align_block = _build_date_alignment_weekend_block(start_str)
        deadline_block = _build_deadline_alignment_block(start_str)
        weekday_hook_block = _build_weekday_hook_alignment_block()
        same_day_event_block = _build_same_post_day_as_event_block(start_str)
        parts.extend([
            "",
            "DATE_CONTEXT (the client's 30 days start on a specific date; use when it adds value):",
            date_context,
            "",
            align_block,
            "",
            deadline_block,
            "",
            weekday_hook_block,
            "",
            same_day_event_block,
            "",
            "When KEY_DATE_EVENTS is also set, prioritize event timing from KEY_DATE_EVENTS over casual weekday mentions. "
            "When only DATE_CONTEXT applies (no KEY_DATE_EVENTS), you may reference weekday/weekend lightly only where it matches **DATE_CONTEXT** "
            "and **WEEKDAY_IN_HOOK_ALIGNMENT** — do not force a calendar date into every caption, but **never** name the wrong weekday in a scene-setting hook. "
            "**DATE_ALIGNMENT**, **DEADLINE_AND_REGISTRATION_ALIGNMENT**, **WEEKDAY_IN_HOOK_ALIGNMENT**, and **SAME_POST_DAY_AS_EVENT** above still apply.",

            "",
            _build_month_narrative_alignment_block(for_stories=False),
        ])

    # Subscription variety: avoid repeating the same day-by-day category pattern as previous packs
    if previous_pack_themes and len(previous_pack_themes) > 0:
        lines = []
        for i, pack in enumerate(previous_pack_themes[:6], 1):  # last 6 packs max
            day_cats = None
            if isinstance(pack, (list, tuple)) and len(pack) >= 30:
                day_cats = [str(c).strip() or "—" for c in pack[:30]]
            elif isinstance(pack, dict) and pack.get("day_categories"):
                raw = list(pack["day_categories"])[:30]
                day_cats = [str(c).strip() or "—" for c in raw]
                while len(day_cats) < 30:
                    day_cats.append("—")
            if day_cats:
                lines.append(f"Previous pack {i}: " + ", ".join(f"D{j+1}:{day_cats[j]}" for j in range(30)))
        if lines:
            parts.extend([
                "",
                "SUBSCRIPTION VARIETY — this client has received previous packs. Previous day-by-day category patterns:",
                *lines,
                "",
                "This month, vary the mix: use a different order and distribution of the five categories so content is not repetitive. Avoid using the same category on the same day number where possible. Keep the same approximate balance (roughly 6 per category) but shuffle which days get which category.",
                "",
                "Also vary the actual content: use different angles, topics, hooks, examples, and phrasing within each category. Do not repeat the same ideas, openers, or proof points they had in previous packs. Each caption should feel fresh and distinct from what they received in earlier months.",
            ])

    parts.extend([
        "",
        "Output the complete markdown document only. No preamble or explanation."
    ])
    return "\n".join(parts) + range_note


def _build_doc_header(intake: Dict[str, Any], pack_start_date: Optional[str] = None) -> str:
    """Build title, subtitle, and intake summary so we can prepend to chunked output. Uses normalized case (no ALL CAPS)."""
    from datetime import datetime
    from services.caption_pdf import pack_month_range_label

    n = _normalize_intake_case
    start_str = (pack_start_date or "").strip() or datetime.utcnow().strftime("%Y-%m-%d")
    month_year = pack_month_range_label(start_str)
    if not month_year:
        try:
            month_year = datetime.strptime(start_str[:10], "%Y-%m-%d").strftime("%B %Y")
        except ValueError:
            month_year = datetime.utcnow().strftime("%B %Y")
    business = n((intake.get("business_name") or "").strip(), sentence_case=False) or "Client"
    audience = n(intake.get("audience") or "", sentence_case=False) or "Not specified"
    voice = n((intake.get("voice_words") or intake.get("voice_avoid") or "").strip(), sentence_case=False) or "Not specified"
    goal = n(intake.get("goal") or "", sentence_case=False) or "Not specified"
    launch_desc = (intake.get("launch_event_description") or "").strip()
    if launch_desc:
        launch_desc = n(launch_desc, sentence_case=True)
    facts_g = (intake.get("facts_guardrails") or "").strip()
    if facts_g:
        facts_g = n(facts_g, sentence_case=True)
    lines = [
        "# 30 Days of Social Media Captions",
        f"{business} | {month_year}",
        "---",
        "INTAKE SUMMARY",
        "---",
        f"- Business: {business}",
        f"- Audience: {audience}",
        f"- Voice: {voice}",
        f"- Language: {intake.get('caption_language', 'English (UK)')}",
        f"- Platform(s): {(intake.get('platform') or '').strip() or 'Not specified'}",
        f"- Goal: {goal}",
    ]
    if _effective_vary_ig_fb_caption_length(intake):
        lines.append("- Instagram & Facebook: varied caption lengths (opt-in)")
    if facts_g:
        lines.append(f"- Facts / constraints: {facts_g}")
    if launch_desc:
        lines.append(f"- Key date: {launch_desc}")
    lines.extend([
        "---",
        "CAPTIONS",
        "---",
    ])
    return "\n".join(lines) + "\n"


def _chunk_has_empty_blocks(content: str, include_hashtags: bool) -> bool:
    """Return True if markdown has empty **Caption:** or **Hashtags:** lines (indicates incomplete AI output)."""
    if not content or "**Caption:**" not in content:
        return True
    # Detect truly empty blocks (allowing blank lines after label). A caption is only empty
    # if there is no non-whitespace text before the next section marker.
    caption_label_re = r"(?:\*\*\s*Caption\s*:\s*\*\*|Caption[ \t]*:)"
    hashtag_label_re = r"(?:\*\*\s*Hashtags?\s*:\s*\*\*|Hashtags?[ \t]*:)"
    platform_label_re = r"(?:\*\*\s*Platform\s*:\s*\*\*|Platform[ \t]*:)"
    for m in re.finditer(caption_label_re, content, re.I):
        start = m.end()
        next_markers = [
            re.search(r"\n\s*" + hashtag_label_re, content[start:], re.I),
            re.search(r"\n\s*" + platform_label_re, content[start:], re.I),
            re.search(r"\n\s*##\s*Day\s+\d+\b", content[start:], re.I),
            re.search(r"\n\s*---\s*$", content[start:], re.I | re.M),
        ]
        next_positions = [start + mm.start() for mm in next_markers if mm]
        end = min(next_positions) if next_positions else len(content)
        if not (content[start:end] or "").strip():
            return True
    if include_hashtags:
        for m in re.finditer(hashtag_label_re, content, re.I):
            start = m.end()
            next_markers = [
                re.search(r"\n\s*" + platform_label_re, content[start:], re.I),
                re.search(r"\n\s*##\s*Day\s+\d+\b", content[start:], re.I),
                re.search(r"\n\s*---\s*$", content[start:], re.I | re.M),
            ]
            next_positions = [start + mm.start() for mm in next_markers if mm]
            end = min(next_positions) if next_positions else len(content)
            if not (content[start:end] or "").strip():
                return True
    return False


def _rough_sentence_count(text: str) -> int:
    """Count sentences (. ! ?) with enough characters to be substantive (not 'OK.' only)."""
    if not (text or "").strip():
        return 0
    chunks = re.split(r"[.!?]+", text)
    return sum(1 for c in chunks if len(c.strip()) >= 12)


def _platform_label_is_tiktok(label: str) -> bool:
    return (label or "").strip().lower() == "tiktok"


def _truthy_intake_flag(val: Any) -> bool:
    if val is True:
        return True
    if val is False or val is None:
        return False
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "on")
    return bool(val)


def _platforms_include_ig_fb(platform_list: Optional[List[str]]) -> bool:
    for p in platform_list or []:
        low = (p or "").lower()
        if "instagram" in low and "facebook" in low:
            return True
    return False


def _effective_vary_ig_fb_caption_length(intake: Dict[str, Any]) -> bool:
    raw = (intake.get("platform") or "").strip()
    pl = [x.strip() for x in raw.split(",") if x.strip()] if raw else []
    return _truthy_intake_flag(intake.get("vary_ig_fb_caption_length")) and _platforms_include_ig_fb(pl)


def _category_from_day_heading_line(line: str) -> str:
    mm = re.match(r"^##\s*Day\s+\d+\s*[—\-]\s*(.+)$", (line or "").strip(), re.I)
    return (mm.group(1).strip() if mm else "")


def _is_engagement_category_heading(cat: str) -> bool:
    c = (cat or "").strip().lower()
    return c == "engagement" or c.startswith("engagement ")


def _engagement_duplicate_hook_overlap(caption_a: str, caption_b: str) -> bool:
    """
    True when two captions reuse the same stale engagement prompt shape (e.g. duplicate
    "what brought you" origin-story asks across different days).
    """
    a, b = (caption_a or "").lower(), (caption_b or "").lower()
    if not a or not b:
        return False
    hooks = (
        "what brought you",
        "what drew you",
        "we'd love to hear your story",
        "was it a recommendation from a friend",
        "we're curious about the journeys that bring",
    )
    for h in hooks:
        if h in a and h in b:
            return True
    return False


_WEEKDAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def _extract_caption_from_platform_block_body(block_body: str) -> str:
    body = block_body or ""
    cap_match = re.search(
        r"(?:\*\*)?Caption(?:\*\*)?\s*:\s*(.+?)(?=(?:\n\s*(?:\*\*)?Hashtags?(?:\*\*)?\s*:)|\Z)",
        body,
        re.I | re.S,
    )
    return (cap_match.group(1).strip() if cap_match else "").strip()


def _iter_day_platform_captions(captions_md: str) -> List[Tuple[int, str, str]]:
    """Yield (day_num, platform_label, caption_text) for each platform block in captions markdown."""
    out: List[Tuple[int, str, str]] = []
    blocks = _split_caption_md_by_day(captions_md)
    for day_num, day_block in sorted(blocks.items()):
        lines = day_block.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            m = re.match(r"(?:\*\*)?Platform(?:\*\*)?\s*:\s*(.+)", line, re.I)
            if not m:
                i += 1
                continue
            platform_raw = (m.group(1) or "").strip()
            start = i + 1
            j = start
            while j < len(lines):
                if re.match(r"(?:\*\*)?Platform(?:\*\*)?\s*:\s*(.+)", lines[j].strip(), re.I):
                    break
                j += 1
            body = "\n".join(lines[start:j]).strip()
            cap = _extract_caption_from_platform_block_body(body)
            if platform_raw and cap:
                out.append((day_num, platform_raw, cap))
            i = j
    return out


def _caption_uses_this_weekday_on_same_calendar_day(caption: str, post_date: date) -> bool:
    """
    True when copy uses “this [Weekday]…” while the post already falls on that weekday
    (SAME_POST_DAY_AS_EVENT — use today / this morning / tonight instead).
    """
    if not caption or not post_date:
        return False
    wname = _WEEKDAY_NAMES[post_date.weekday()]
    t = caption.lower()
    if re.search(rf"(?is)\bthis\s+{re.escape(wname)}\b", t):
        return True
    if re.search(rf"(?is)\bjoin\s+us\s+this\s+{re.escape(wname)}\b", t):
        return True
    if re.search(rf"(?is)\bcome\s+this\s+{re.escape(wname)}\b", t):
        return True
    return False


def _calendar_weekday_alignment_error(captions_md: str, pack_start_date: str) -> Optional[str]:
    """
    Fail validation when any **Caption:** uses “This Friday…”, “Join us this Tuesday…”, etc.
    on a calendar day that is already that weekday (must use this morning / today / tonight).
    """
    if not captions_md or not pack_start_date:
        return None
    try:
        start = datetime.strptime(pack_start_date.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    for day_num, _platform, caption in _iter_day_platform_captions(captions_md):
        post_date = start + timedelta(days=day_num - 1)
        if _caption_uses_this_weekday_on_same_calendar_day(caption, post_date):
            return (
                f"Day {day_num} ({post_date.strftime('%a %d %b %Y')}) uses 'this [weekday]' while the post is already "
                "that weekday — use **this morning / today / tonight** instead of **this [Weekday]** "
                "(SAME_POST_DAY_AS_EVENT)."
            )
    return None


def _april_month_wrap_on_non_april_calendar_day(caption: str, post_date: date) -> bool:
    """
    True when copy frames April as the month being wrapped up while the post day is not in April.
    """
    if not caption or not post_date or post_date.month == 4:
        return False
    tl = caption.lower()
    phrases = (
        "close out april",
        "closing out april",
        "as we close out april",
        "april draws to a close",
        "as april draws to a close",
        "at the end of april",
        "the end of april",
        "throughout april, we",
        "throughout april we've",
        "throughout april we",
        "all april long",
        # Month-wrap / thank-you phrasing that names April as the period being summed up (wrong on a May calendar day).
        "april has been",
        "wrap: april",
    )
    return any(p in tl for p in phrases)


def _caption_month_calendar_alignment_error(captions_md: str, pack_start_date: str) -> Optional[str]:
    """
    Fail when month wrap-up copy (e.g. 'closing out April') appears on a DATE_CONTEXT day in May+.
    """
    if not captions_md or not pack_start_date:
        return None
    try:
        start = datetime.strptime(pack_start_date.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    for day_num, _platform, caption in _iter_day_platform_captions(captions_md):
        post_date = start + timedelta(days=day_num - 1)
        if _april_month_wrap_on_non_april_calendar_day(caption, post_date):
            return (
                f"Day {day_num} ({post_date.strftime('%a %d %b %Y')}) treats April as the current/closing month "
                "but that calendar day is not in April — align month references with **DATE_CONTEXT** for that day "
                "(MONTH_NARRATIVE_ALIGNMENT)."
            )
    return None


def _stories_month_calendar_alignment_error(stories_md: str, pack_start_date: str) -> Optional[str]:
    """
    Same rule as captions: no April-as-current-month wrap on a DATE_CONTEXT day outside April.
    """
    if not stories_md or not pack_start_date:
        return None
    try:
        start = datetime.strptime(pack_start_date.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    day_pat = r"(?:\*\*)?Day\s+(\d+)\s*:(?:\*\*)?"
    for m in re.finditer(
        day_pat + r"\s*(.*?)(?=\s*" + day_pat + r"|$)",
        stories_md,
        re.I | re.DOTALL,
    ):
        day_num = int(m.group(1))
        content = (m.group(2) or "").strip()
        if not (1 <= day_num <= 30):
            continue
        idea_m = re.search(r"\bIdea\s*:\s*(.+?)(?=\bSuggested wording\s*:|\Z)", content, re.I | re.S)
        sugg_m = re.search(r"\bSuggested wording\s*:\s*(.+?)(?=\bStory hashtags\s*:|\bHashtags?\s*:|\Z)", content, re.I | re.S)
        idea = (idea_m.group(1).strip() if idea_m else "")
        suggested = (sugg_m.group(1).strip() if sugg_m else "")
        combined = f"{idea}\n{suggested}"
        post_date = start + timedelta(days=day_num - 1)
        if _april_month_wrap_on_non_april_calendar_day(combined, post_date):
            return (
                f"Story Day {day_num} ({post_date.strftime('%a %d %b %Y')}) frames April as the current/closing month "
                "but that calendar day is not in April — align month references with **DATE_CONTEXT** for that day "
                "(MONTH_NARRATIVE_ALIGNMENT)."
            )
    return None


_EN_MONTH_FULL = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)


def _story_month_future_framing_mismatch(text: str, post_date: date) -> bool:
    """
    True when English copy frames the current calendar month as still 'coming' while the post day is already in that month.
    e.g. Day 23 = Fri 01 May 2026 + 'May is coming'.
    """
    if not text or not post_date:
        return False
    tl = text.lower()
    mnum = post_date.month
    name = _EN_MONTH_FULL[mnum - 1]
    if name == "may":
        patterns = (
            r"\bmay\s+is\s+coming\b",
            r"\bmay\s+is\s+almost\s+here\b",
            r"\bheading\s+into\s+may\b",
            r"\bas\s+may\s+approaches\b",
        )
        return any(re.search(p, tl) for p in patterns)
    n = re.escape(name)
    patterns = (
        rf"\b{n}\s+is\s+coming\b",
        rf"\b{n}\s+is\s+almost\s+here\b",
        rf"\bheading\s+into\s+{n}\b",
        rf"\bas\s+{n}\s+approaches\b",
    )
    return any(re.search(p, tl) for p in patterns)


def _stories_month_future_framing_error(stories_md: str, pack_start_date: str) -> Optional[str]:
    """Reject stories where Idea/Suggested wording say 'May is coming' on a day already in May, etc."""
    if not stories_md or not pack_start_date:
        return None
    try:
        start = datetime.strptime(pack_start_date.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    day_pat = r"(?:\*\*)?Day\s+(\d+)\s*:(?:\*\*)?"
    for m in re.finditer(
        day_pat + r"\s*(.*?)(?=\s*" + day_pat + r"|$)",
        stories_md,
        re.I | re.DOTALL,
    ):
        day_num = int(m.group(1))
        content = (m.group(2) or "").strip()
        if not (1 <= day_num <= 30):
            continue
        idea_m = re.search(r"\bIdea\s*:\s*(.+?)(?=\bSuggested wording\s*:|\Z)", content, re.I | re.S)
        sugg_m = re.search(r"\bSuggested wording\s*:\s*(.+?)(?=\bStory hashtags\s*:|\bHashtags?\s*:|\Z)", content, re.I | re.S)
        idea = (idea_m.group(1).strip() if idea_m else "")
        suggested = (sugg_m.group(1).strip() if sugg_m else "")
        combined = f"{idea}\n{suggested}"
        post_date = start + timedelta(days=day_num - 1)
        if _story_month_future_framing_mismatch(combined, post_date):
            return (
                f"Story Day {day_num} ({post_date.strftime('%a %d %b %Y')}) treats that calendar month as still "
                "'coming' but the post is already in that month — use **this month**, **early [Month]**, or **what's new** "
                "(STORY_POSTING_DAY_ALIGNMENT)."
            )
    return None


def _platform_label_is_instagram_facebook(label: str) -> bool:
    """True when **Platform:** matches the combined Instagram & Facebook product label (after normalization)."""
    s = (label or "").strip().lower()
    s = re.sub(r"\s*&\s*", " and ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s == "instagram and facebook"


def _chunk_structure_error(
    content: str,
    day_start: int,
    day_end: int,
    expected_platform_count: int,
    expected_platform_labels: Optional[list] = None,
    include_hashtags: bool = True,
    hashtag_min: int = 3,
    hashtag_max: int = 10,
    vary_ig_fb_caption_length: bool = False,
) -> Optional[str]:
    """
    Return a validation error string for bad chunk structure, else None.
    Enforces:
    - every expected day heading appears once
    - each day has exactly expected_platform_count platform blocks
    - no duplicate platform label within the same day
    - hashtags count and basic content sanity
    - near-duplicate caption text within the same chunk (stricter for Engagement + same platform;
      plus blocked duplicate hooks like repeated "what brought you" across Engagement days)
    """
    if not content:
        return "Chunk is empty."
    expected_days = set(range(day_start, day_end + 1))
    day_matches = list(
        re.finditer(r"^##\s*Day\s+(\d+)\s*[—\-].*$", content, re.I | re.M)
    )
    found_days = []
    blocks_by_day = {}
    for idx, m in enumerate(day_matches):
        day_num = int(m.group(1))
        found_days.append(day_num)
        start = m.end()
        end = day_matches[idx + 1].start() if idx + 1 < len(day_matches) else len(content)
        blocks_by_day[day_num] = content[start:end]

    missing = sorted(expected_days - set(found_days))
    if missing:
        return f"Missing day headings in chunk: {missing}"
    duplicates = sorted({d for d in found_days if found_days.count(d) > 1 and d in expected_days})
    if duplicates:
        return f"Duplicate day headings in chunk: {duplicates}"
    unexpected = sorted(d for d in set(found_days) if d not in expected_days)
    if unexpected:
        return f"Unexpected day headings in chunk: {unexpected}"

    category_by_day: Dict[int, str] = {}
    for m in day_matches:
        try:
            dn = int(m.group(1))
        except (ValueError, IndexError):
            continue
        category_by_day[dn] = _category_from_day_heading_line(m.group(0))

    def _canonical_platform_label(raw: str) -> str:
        s = (raw or "").replace("*", "").strip().lower()
        if not s:
            return ""
        # Normalize punctuation/joins for robust dedupe checks.
        s = re.sub(r"\s*&\s*", " and ", s)
        s = re.sub(r"\s+", " ", s).strip()
        # Canonicalize IG+FB combinations.
        compact = s.replace(" ", "")
        if compact in ("instagramandfacebook", "facebookandinstagram"):
            return "instagram and facebook"
        # If expected platform list exists, map close variants to expected labels.
        for p in (expected_platform_labels or []):
            pp = (p or "").strip().lower()
            pp_norm = re.sub(r"\s*&\s*", " and ", pp)
            pp_norm = re.sub(r"\s+", " ", pp_norm).strip()
            if pp_norm and (s == pp_norm or s.replace(" ", "") == pp_norm.replace(" ", "")):
                return pp_norm
        return s

    def _extract_blocks(day_block: str) -> list:
        blocks = []
        lines = day_block.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            m = re.match(r"(?:\*\*)?Platform(?:\*\*)?\s*:\s*(.+)", line, re.I)
            if not m:
                i += 1
                continue
            platform_raw = (m.group(1) or "").strip()
            start = i + 1
            j = start
            while j < len(lines):
                if re.match(r"(?:\*\*)?Platform(?:\*\*)?\s*:\s*(.+)", lines[j].strip(), re.I):
                    break
                j += 1
            body = "\n".join(lines[start:j]).strip()
            blocks.append({"platform": platform_raw, "body": body})
            i = j
        return blocks

    def _extract_caption_and_hashtags(block_body: str) -> Tuple[str, str]:
        body = block_body or ""
        cap_match = re.search(r"(?:\*\*)?Caption(?:\*\*)?\s*:\s*(.+?)(?=(?:\n\s*(?:\*\*)?Hashtags?(?:\*\*)?\s*:)|\Z)", body, re.I | re.S)
        caption = (cap_match.group(1).strip() if cap_match else "").strip()
        hash_match = re.search(r"(?:\*\*)?Hashtags?(?:\*\*)?\s*:\s*(.+)$", body, re.I | re.S)
        hashtags = (hash_match.group(1).strip() if hash_match else "").strip()
        return caption, hashtags

    def _normalize_caption_for_similarity(text: str) -> str:
        t = (text or "").lower()
        t = re.sub(r"#[a-z0-9_]+", "", t)
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    def _has_placeholder(text: str) -> bool:
        t = (text or "").lower()
        return any(k in t for k in ["lorem ipsum", "tbd", "[insert", "coming soon", "placeholder"])

    def _count_hashtags(text: str) -> int:
        if not text:
            return 0
        return len(re.findall(r"#[a-z0-9_]+", text, re.I))

    similarity_texts = []
    for day_num in sorted(expected_days):
        block = blocks_by_day.get(day_num, "")
        blocks = _extract_blocks(block)
        platforms = []
        seen = set()
        dup_platforms = []
        if len(blocks) != expected_platform_count:
            return (
                f"Day {day_num} has {len(blocks)} platform block(s); "
                f"expected {expected_platform_count}"
            )
        for b in blocks:
            label = _canonical_platform_label(b.get("platform") or "")
            if not label:
                continue
            platforms.append(label)
            if label in seen:
                dup_platforms.append(label)
            else:
                seen.add(label)
            caption, hashtags = _extract_caption_and_hashtags(b.get("body") or "")
            if not caption:
                return f"Day {day_num} ({label}) missing caption text"
            # Basic quality guardrails (platform-aware minimum length + substance).
            is_tiktok = _platform_label_is_tiktok(label)
            is_ig_fb = _platform_label_is_instagram_facebook(label)
            if is_tiktok:
                min_len = 30
            elif vary_ig_fb_caption_length and is_ig_fb:
                min_len = 100
            else:
                min_len = 200
            if len(caption) < min_len:
                return (
                    f"Day {day_num} ({label}) caption too short "
                    f"(min {min_len} characters for this platform)"
                )
            if not is_tiktok:
                rs = _rough_sentence_count(caption)
                if vary_ig_fb_caption_length and is_ig_fb:
                    if rs < 1:
                        return (
                            f"Day {day_num} ({label}) caption must have at least one complete sentence "
                            f"with specifics (not a vague fragment)"
                        )
                    if rs < 2 and len(caption) < 125:
                        return (
                            f"Day {day_num} ({label}) short Instagram & Facebook posts must still be substantive "
                            f"(min 125 characters when using a single sentence)"
                        )
                elif rs < 2:
                    return (
                        f"Day {day_num} ({label}) caption must have at least 2 complete sentences "
                        f"with specifics (not a one-liner or vague fragment)"
                    )
            if _has_placeholder(caption):
                return f"Day {day_num} ({label}) caption contains placeholder text"
            if include_hashtags:
                n_hash = _count_hashtags(hashtags)
                if n_hash < hashtag_min or n_hash > hashtag_max:
                    return (
                        f"Day {day_num} ({label}) has {n_hash} hashtags; "
                        f"expected {hashtag_min}-{hashtag_max}"
                    )
            similarity_texts.append((day_num, label, _normalize_caption_for_similarity(caption)))
        if dup_platforms:
            return f"Day {day_num} has duplicate platform blocks: {sorted(set(dup_platforms))}"
    # Near-duplicate detection across whole chunk (stricter for Engagement + same platform).
    for i in range(len(similarity_texts)):
        d1, p1, t1 = similarity_texts[i]
        for j in range(i + 1, len(similarity_texts)):
            d2, p2, t2 = similarity_texts[j]
            if not t1 or not t2:
                continue
            cat1 = category_by_day.get(d1, "")
            cat2 = category_by_day.get(d2, "")
            both_eng = _is_engagement_category_heading(cat1) and _is_engagement_category_heading(cat2)
            same_plat = (p1 or "").strip().lower() == (p2 or "").strip().lower()
            if (
                both_eng
                and same_plat
                and d1 != d2
                and _engagement_duplicate_hook_overlap(t1, t2)
            ):
                return (
                    f"Engagement captions repeat the same prompt pattern: Day {d1} ({p1}) and Day {d2} ({p2})"
                )
            ratio = SequenceMatcher(None, t1, t2).ratio()
            thresh = 0.78 if (both_eng and same_plat) else 0.92
            if ratio >= thresh:
                return (
                    f"Near-duplicate captions detected: Day {d1} ({p1}) and Day {d2} ({p2})"
                )
    return None


def _strip_stories_section_from_captions_md(md: str) -> str:
    """Remove Story Ideas appendix so day-splitting only sees caption days."""
    if not md:
        return md
    idx = md.find("\n## 30 Story Ideas")
    if idx == -1:
        idx = md.find("\n## 30 story ideas")
    return md[:idx] if idx != -1 else md


def _split_caption_md_by_day(md: str) -> Dict[int, str]:
    """Map day number (1–30) to markdown block starting at ## Day N."""
    md = _strip_stories_section_from_captions_md(md)
    blocks: Dict[int, str] = {}
    pat = re.compile(r"^##\s*Day\s+(\d+)\s*[—\-]", re.M)
    matches = list(pat.finditer(md))
    for i, m in enumerate(matches):
        try:
            day_num = int(m.group(1))
        except ValueError:
            continue
        if not (1 <= day_num <= 30):
            continue
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        blocks[day_num] = md[start:end]
    return blocks


def _calendar_date_from_day_month(day: int, month_word: str, year: int) -> Optional[date]:
    mw = (month_word or "").strip().lower()
    if not mw:
        return None
    for full_name, mnum in _MONTH_NUM.items():
        if full_name == mw or full_name.startswith(mw[: min(3, len(mw))]):
            try:
                return date(year, mnum, day)
            except ValueError:
                return None
    return None


def _has_future_deadline_before_post_day(text: str, post_date: date) -> bool:
    """
    True if copy uses future-style registration/close wording tied to a calendar date
    strictly before post_date (incoherent on the post day).
    """
    if not text or not post_date:
        return False
    tl = text.lower()
    if re.search(
        r"\b(already\s+closed|has\s+closed|have\s+closed|registration\s+(?:has\s+)?ended|"
        r"early[- ]bird\s+(?:has\s+)?ended|past\s+the\s+early[- ]bird|"
        r"early[- ]bird\s+window\s+(?:has\s+)?closed|you\s+missed\s+the\s+early[- ]bird)\b",
        tl,
    ):
        return False
    year = post_date.year
    patterns = [
        # registration closes on 8 April / early-bird registration closes on 8 April
        (
            re.compile(
                r"(?is)\b(?:early[- ]bird\s+)?registration\s+closes\s*(?:on|by|before)?\s*(?:the\s+)?"
                r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\b"
            ),
            "dm",
        ),
        (
            re.compile(
                r"(?is)\bcloses\s+on\s+(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?"
                r"(january|february|march|april|may|june|july|august|september|october|november|december)\b"
            ),
            "dm",
        ),
        (
            re.compile(
                r"(?is)\b(?:early[- ]bird\s+)?registration\s+closes\s+(?:on|by|before)?\s*"
                r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+"
                r"(\d{1,2})(?:st|nd|rd|th)?\b"
            ),
            "md",
        ),
        (
            re.compile(
                r"(?is)\bearly[- ]bird\s+(?:registration\s+)?(?:closes|ends)\s*(?:on|by)?\s*"
                r"(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b"
            ),
            "dm",
        ),
        (
            re.compile(
                r"(?is)\bregister\s+(?:by|before)\s*(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+"
                r"(january|february|march|april|may|june|july|august|september|october|november|december)\b"
            ),
            "dm",
        ),
    ]
    for rx, mode in patterns:
        for m in rx.finditer(text):
            if mode == "dm":
                d_, mo = int(m.group(1)), m.group(2)
            else:
                mo, d_ = m.group(1), int(m.group(2))
            dt = _calendar_date_from_day_month(d_, mo, year)
            if dt and dt < post_date:
                return True
    return False


def _validate_deadline_vs_post_dates(captions_md: str, pack_start_date: str) -> List[str]:
    """Warn when a day's caption implies a live deadline before that day's calendar date."""
    warnings: List[str] = []
    if not captions_md or not pack_start_date:
        return warnings
    try:
        start = datetime.strptime(pack_start_date.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return warnings
    blocks = _split_caption_md_by_day(captions_md)
    for day_num in range(1, 31):
        block = blocks.get(day_num)
        if not block:
            continue
        post_date = start + timedelta(days=day_num - 1)
        if _has_future_deadline_before_post_day(block, post_date):
            warnings.append(
                f"Quality check: Day {day_num} ({post_date.strftime('%a %d %b %Y')}) may state a "
                f"registration/deadline as still upcoming on a date before the post day — revise tense or dates "
                f"(DEADLINE_AND_REGISTRATION_ALIGNMENT)."
            )
    return warnings


def _validate_caption_quality(
    captions_md: str, intake: Dict[str, Any], pack_start_date: str
) -> list:
    """
    Post-generation validation. Returns list of warning strings.
    Catches detectable quality issues (e.g. launch-day content referencing wrong dates).
    Does not block delivery; caller may log warnings.
    """
    warnings = []
    launch_desc = (intake.get("launch_event_description") or "").strip()
    if not launch_desc:
        return warnings
    bounds = _resolve_event_pack_bounds(pack_start_date, launch_desc)
    if bounds:
        da_b, db_b, _, _ = bounds
        if not _event_calendar_allows_weekend_phrase(da_b, db_b) and re.search(
            r"\b(this|next)\s+weekend\b", captions_md, re.I
        ):
            warnings.append(
                "Quality check: Caption text uses “this weekend” or “next weekend” but the "
                "EVENT_CALENDAR is not a Saturday–Sunday event—review wording against DATE_CONTEXT."
            )
    key_date_day = _parse_key_date_from_text(launch_desc, pack_start_date)
    if key_date_day is None:
        return warnings
    try:
        start = datetime.strptime((pack_start_date or "")[:10], "%Y-%m-%d")
        launch_date = start + timedelta(days=key_date_day - 1)
        expected_month = launch_date.strftime("%B").lower()  # e.g. "march"
        month_order = [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ]
        expected_idx = month_order.index(expected_month) if expected_month in month_order else -1
    except (ValueError, TypeError):
        return warnings

    # Extract content for launch day: ## Day N caption blocks and **Day N:** story lines
    day_content = []
    in_day_block = False
    current_day = 0
    for line in captions_md.splitlines():
        m = re.match(r"^##\s*Day\s+(\d+)\s*[—\-]", line.strip())
        if m:
            current_day = int(m.group(1))
            in_day_block = current_day == key_date_day
            if in_day_block:
                day_content.append(line)
            continue
        m2 = re.match(r"^\*\*Day\s+(\d+):\*\*", line.strip())
        if m2 and int(m2.group(1)) == key_date_day:
            day_content.append(line)
            continue
        if in_day_block and current_day == key_date_day:
            # Still in caption block for this day (until next ## Day)
            day_content.append(line)

    text = " ".join(day_content).lower()

    # Wrong month: launch day says "april" when launch is March
    wrong_months = []
    for m in month_order:
        if m == expected_month:
            continue
        if m in text:
            wrong_months.append(m)
    if wrong_months and expected_idx >= 0:
        # Allow "march and april" or "through april" (range) but flag "opens april" style
        wrong_date_phrases = [
            r"opens?\s+(in\s+)?(" + "|".join(wrong_months) + r")",
            r"(" + "|".join(wrong_months) + r")\s+\d{1,2}",
            r"\d{1,2}\s+(" + "|".join(wrong_months) + r")",  # e.g. "4 April"
            r"(in|on)\s+(" + "|".join(wrong_months) + r")",
            r"mark\s+(your\s+)?calendars?\s+for\s+(" + "|".join(wrong_months) + r")",
        ]
        for pat in wrong_date_phrases:
            if re.search(pat, text):
                warnings.append(
                    f"Quality check: Launch day (Day {key_date_day}) may reference wrong month. "
                    f"Expected {expected_month}; found reference to {wrong_months}. "
                    f"Review CAPTION_QUALITY_STANDARDS.md and STORY_QUALITY_STANDARDS.md."
                )
                break
    return warnings


def _validate_story_quality(stories_md: str) -> list:
    """
    Post-generation validation for story output. Returns list of warning strings.
    Catches completeness issues (missing days, empty Idea/Suggested wording).
    Does not block delivery; caller may log warnings.
    """
    warnings = []
    if not stories_md or not re.search(r"(?:\*\*)?Day\s+\d+\s*:(?:\*\*)?", stories_md, re.I):
        return warnings
    found_days = set()
    day_pat = r"(?:\*\*)?Day\s+(\d+)\s*:(?:\*\*)?"
    for m in re.finditer(
        day_pat + r"\s*(.*?)(?=\s*" + day_pat + r"|$)",
        stories_md,
        re.I | re.DOTALL,
    ):
        day_num = int(m.group(1))
        content = (m.group(2) or "").strip()
        if 1 <= day_num <= 30:
            found_days.add(day_num)
        if not content:
            warnings.append(f"Quality check: Story Day {day_num} has no content.")
            continue
        if "idea:" not in content.lower():
            warnings.append(f"Quality check: Story Day {day_num} missing Idea.")
        if "suggested wording:" not in content.lower():
            warnings.append(f"Quality check: Story Day {day_num} missing Suggested wording.")
        if "story hashtags:" not in content.lower() and "hashtags:" not in content.lower():
            warnings.append(f"Quality check: Story Day {day_num} missing Story hashtags.")
    missing = set(range(1, 31)) - found_days
    if missing:
        warnings.append(f"Quality check: Story ideas missing days: {sorted(missing)[:10]}{'...' if len(missing) > 10 else ''}.")
    return warnings


def _stories_structure_error(
    stories_md: str,
    *,
    hashtag_min: int = 3,
    hashtag_max: int = 10,
) -> Optional[str]:
    """
    Strict validator for stories markdown section.
    Enforces:
    - exactly 30 story days (1..30), each once
    - each day has Idea, Suggested wording, Story hashtags
    - hashtag count per day within bounds
    - no near-duplicate suggested wording across days
    """
    if not stories_md or not re.search(r"(?:\*\*)?Day\s+\d+\s*:(?:\*\*)?", stories_md, re.I):
        return "Stories output is empty or missing day entries"

    day_pat = r"(?:\*\*)?Day\s+(\d+)\s*:(?:\*\*)?"
    day_entries = list(
        re.finditer(
            day_pat + r"\s*(.*?)(?=\s*" + day_pat + r"|$)",
            stories_md,
            re.I | re.DOTALL,
        )
    )
    if len(day_entries) != 30:
        return f"Stories output has {len(day_entries)} day entries; expected 30"

    day_nums = []
    suggested_by_day = {}
    for m in day_entries:
        day_num = int(m.group(1))
        content = (m.group(2) or "").strip()
        day_nums.append(day_num)
        if not content:
            return f"Story Day {day_num} has no content"

        idea_m = re.search(r"\bIdea\s*:\s*(.+?)(?=\bSuggested wording\s*:|\Z)", content, re.I | re.S)
        sugg_m = re.search(r"\bSuggested wording\s*:\s*(.+?)(?=\bStory hashtags\s*:|\bHashtags?\s*:|\Z)", content, re.I | re.S)
        hash_m = re.search(r"\b(?:Story hashtags|Hashtags?)\s*:\s*(.+)$", content, re.I | re.S)
        idea = (idea_m.group(1).strip() if idea_m else "")
        suggested = (sugg_m.group(1).strip() if sugg_m else "")
        hashtags = (hash_m.group(1).strip() if hash_m else "")

        if not idea:
            return f"Story Day {day_num} missing Idea"
        if not suggested:
            return f"Story Day {day_num} missing Suggested wording"
        if not hashtags:
            return f"Story Day {day_num} missing Story hashtags"

        hashtag_count = len(re.findall(r"#[a-z0-9_]+", hashtags, re.I))
        if hashtag_count < hashtag_min or hashtag_count > hashtag_max:
            return (
                f"Story Day {day_num} has {hashtag_count} hashtags; "
                f"expected {hashtag_min}-{hashtag_max}"
            )

        normalized = re.sub(r"\s+", " ", suggested.lower()).strip()
        suggested_by_day[day_num] = normalized

    if sorted(day_nums) != list(range(1, 31)):
        return "Stories output does not contain exactly Day 1 to Day 30 once each"

    # Near-duplicate suggested wording check.
    pairs = sorted(suggested_by_day.items(), key=lambda x: x[0])
    for i in range(len(pairs)):
        d1, t1 = pairs[i]
        for j in range(i + 1, len(pairs)):
            d2, t2 = pairs[j]
            if not t1 or not t2:
                continue
            if SequenceMatcher(None, t1, t2).ratio() >= 0.92:
                return f"Near-duplicate story wording detected: Day {d1} and Day {d2}"
    return None


class CaptionGenerator:
    """Generate 30 captions from intake using AI. Uses 3 chunks to avoid timeouts and token limits."""

    CHUNKS = [(1, 10), (11, 20), (21, 30)]
    MAX_TOKENS_PER_CHUNK = 6000

    def __init__(self):
        provider = (Config.AI_PROVIDER or "openai").strip().lower()
        if provider == "anthropic":
            if not Config.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not configured (set AI_PROVIDER=anthropic)")
        else:
            if not Config.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not configured")

    def generate(self, intake: Dict[str, Any], previous_pack_themes: Optional[list] = None, pack_start_date: Optional[str] = None) -> str:
        """
        Generate full 30-day caption document as markdown in 3 API calls (days 1–10, 11–20, 21–30).
        If include_stories and platform has Instagram & Facebook, appends 30 Story prompts.
        previous_pack_themes: for subscriptions, list of previous packs' day categories.
        pack_start_date: YYYY-MM-DD so Day 1 = this date (default: today UTC). Ensures key-date phasing aligns.
        Raises on API error.
        """
        start_str = (pack_start_date or "").strip() or datetime.utcnow().strftime("%Y-%m-%d")
        include_hashtags = intake.get("include_hashtags", True)
        if isinstance(include_hashtags, str) and include_hashtags.lower() in ("false", "0", "no", "off"):
            include_hashtags = False
        platform_raw = (intake.get("platform") or "").strip()
        platform_list = [p.strip() for p in platform_raw.split(",") if p.strip()]
        expected_platform_count = max(1, len(platform_list)) if platform_list else 1
        hashtag_min = max(1, min(30, int(intake.get("hashtag_min") or 3)))
        hashtag_max = max(0, min(30, int(intake.get("hashtag_max") or 10)))
        if hashtag_min > hashtag_max:
            hashtag_max = hashtag_min
        vary_ig_fb = _effective_vary_ig_fb_caption_length(intake)
        system = _build_system_prompt(intake)
        header = _build_doc_header(intake, pack_start_date=start_str)
        full_pack_suffix = ""
        result = ""
        for full_attempt in range(2):
            parts = [header]
            for day_start, day_end in self.CHUNKS:
                user = (
                    _build_user_prompt(
                        intake,
                        day_start=day_start,
                        day_end=day_end,
                        previous_pack_themes=previous_pack_themes,
                        pack_start_date=start_str,
                    )
                    + full_pack_suffix
                )
                content = chat_completion(
                    system=system,
                    user=user,
                    temperature=0.6,
                    max_tokens=self.MAX_TOKENS_PER_CHUNK,
                )
                if not content:
                    raise RuntimeError(f"AI returned empty content for days {day_start}-{day_end}")
                # Retry up to 3 times if chunk has incomplete/invalid structure
                # (empty blocks, missing day/platform, duplicates). This reduces
                # transient provider-format failures that otherwise block delivery.
                chunk_err = None
                for attempt in range(3):
                    chunk_err = _chunk_structure_error(
                        content,
                        day_start,
                        day_end,
                        expected_platform_count,
                        expected_platform_labels=platform_list,
                        include_hashtags=bool(include_hashtags),
                        hashtag_min=hashtag_min,
                        hashtag_max=hashtag_max,
                        vary_ig_fb_caption_length=vary_ig_fb,
                    )
                    has_empty = _chunk_has_empty_blocks(content, include_hashtags)
                    if not has_empty and not chunk_err:
                        break
                    if attempt >= 2:
                        suffix = f" ({chunk_err})" if chunk_err else " (empty Caption or Hashtags)"
                        raise RuntimeError(
                            f"AI still returned incomplete content for days {day_start}-{day_end}{suffix}. Please try again."
                        )
                    reason = chunk_err or "empty Caption/Hashtags lines"
                    if vary_ig_fb:
                        length_retry = (
                            "For **Instagram & Facebook** this client opted into varied lengths: mix short, medium, and slightly longer feed posts across days—"
                            "each **Caption:** still standalone-clear (what they offer, who it is for). "
                            "Single-sentence IG/FB days must be at least ~125 characters with concrete detail; "
                            "two-or-more-sentence days at least ~100 characters total. "
                            "For other platforms (LinkedIn, Pinterest, etc.), keep ~200+ characters and multiple sentences unless TikTok."
                        )
                    else:
                        length_retry = (
                            "For Instagram, Facebook, LinkedIn, Pinterest: each **Caption:** must be at least ~200 characters "
                            "and at least two full sentences with concrete detail—no vague one-line fragments."
                        )
                    retry_user = user + (
                        "\n\nIMPORTANT: Your previous response was invalid (" + reason + "). "
                        "Regenerate this range exactly with strict structure: "
                        "each expected day heading once, one platform block per platform per day, "
                        "no duplicate platform blocks in a day, and no empty **Caption:** or **Hashtags:** lines. "
                        "If hashtags are requested, each **Hashtags:** line must contain real hashtags starting with # "
                        f"and the count must be between {hashtag_min} and {hashtag_max}. "
                        + length_retry
                    )
                    content = chat_completion(
                        system=system,
                        user=retry_user,
                        temperature=0.35,
                        max_tokens=self.MAX_TOKENS_PER_CHUNK,
                    )
                    if not content:
                        raise RuntimeError(f"AI returned empty content on retry for days {day_start}-{day_end}")
                parts.append(content)
            result = "\n".join(parts)
            # Cross-chunk checks (e.g. Engagement day 4 vs day 14): per-chunk validation cannot see both.
            captions_only = _strip_stories_section_from_captions_md(result)
            full_err = _chunk_structure_error(
                captions_only,
                1,
                30,
                expected_platform_count,
                expected_platform_labels=platform_list,
                include_hashtags=bool(include_hashtags),
                hashtag_min=hashtag_min,
                hashtag_max=hashtag_max,
                vary_ig_fb_caption_length=vary_ig_fb,
            )
            if not full_err:
                full_err = _calendar_weekday_alignment_error(captions_only, start_str)
            if not full_err:
                full_err = _caption_month_calendar_alignment_error(captions_only, start_str)
            if not full_err:
                break
            if full_attempt >= 1:
                raise RuntimeError(
                    f"Caption pack failed full 30-day validation: {full_err}. Please try again."
                )
            full_pack_suffix = (
                "\n\nIMPORTANT — full 30-day pack validation failed: "
                + full_err
                + " Regenerate all three day ranges with that fixed. "
                "If the error is about **this [weekday]** vs **DATE_CONTEXT**: when the post goes live on the **same** "
                "calendar day as the class or event, open with **this morning / today / tonight** — never "
                "**This Friday morning** (etc.) on a Friday post. "
                "If the error is about **month** vs **DATE_CONTEXT**: each Day N’s **Caption:** must match the **calendar month** "
                "of that day’s line in DATE_CONTEXT — do not write “close out April” on a day that is already in May. "
                "Engagement days must use different hooks across the month; do not duplicate origin-story question patterns."
            )

        # Stories add-on: when IG & FB selected and include_stories
        platform_raw = (intake.get("platform") or "").strip().lower()
        include_stories = bool(intake.get("include_stories"))
        align_stories = bool(intake.get("align_stories_to_captions"))
        has_ig_fb = "instagram" in platform_raw or "facebook" in platform_raw
        if include_stories and has_ig_fb:
            if align_stories:
                stories_md = self._generate_stories_aligned(
                    intake,
                    result,
                    is_subscription_variety=bool(previous_pack_themes),
                    pack_start_date=start_str,
                )
            else:
                stories_md = self._generate_stories(
                    intake,
                    is_subscription_variety=bool(previous_pack_themes),
                    pack_start_date=start_str,
                )
            if stories_md:
                story_err = _stories_structure_error(
                    stories_md,
                    hashtag_min=hashtag_min,
                    hashtag_max=hashtag_max,
                )
                if not story_err:
                    story_err = _stories_month_calendar_alignment_error(stories_md, start_str)
                if not story_err:
                    story_err = _stories_month_future_framing_error(stories_md, start_str)
                if story_err:
                    stories_md = self._generate_stories_with_retry(
                        intake,
                        align_stories=align_stories,
                        captions_md=result if align_stories else None,
                        is_subscription_variety=bool(previous_pack_themes),
                        pack_start_date=start_str,
                        hashtag_min=hashtag_min,
                        hashtag_max=hashtag_max,
                        reason=story_err,
                    )
                result = result + "\n\n" + stories_md
                for w in _validate_story_quality(stories_md):
                    print(f"[CaptionGenerator] Story quality warning: {w}")

        # Post-generation validation: log quality warnings (does not block delivery)
        for w in _validate_caption_quality(result, intake, start_str):
            print(f"[CaptionGenerator] Quality warning: {w}")
        for w in _validate_deadline_vs_post_dates(result, start_str):
            print(f"[CaptionGenerator] Quality warning: {w}")

        return result

    def _generate_stories_with_retry(
        self,
        intake: Dict[str, Any],
        *,
        align_stories: bool,
        captions_md: Optional[str],
        is_subscription_variety: bool,
        pack_start_date: Optional[str],
        hashtag_min: int,
        hashtag_max: int,
        reason: str,
    ) -> str:
        """
        Retry stories generation once with strict format instructions.
        Raises RuntimeError if still invalid.
        """
        if align_stories:
            stories_md = self._generate_stories_aligned(
                intake,
                captions_md or "",
                is_subscription_variety=is_subscription_variety,
                pack_start_date=pack_start_date,
                strict_note=(
                    "Previous stories output failed validation: "
                    + reason
                    + ". Regenerate exactly Day 1-30 once each with complete Idea/Suggested wording/Story hashtags."
                ),
            )
        else:
            stories_md = self._generate_stories(
                intake,
                is_subscription_variety=is_subscription_variety,
                pack_start_date=pack_start_date,
                strict_note=(
                    "Previous stories output failed validation: "
                    + reason
                    + ". Regenerate exactly Day 1-30 once each with complete Idea/Suggested wording/Story hashtags."
                ),
            )
        if not stories_md:
            raise RuntimeError("Stories generation failed on retry (empty output)")
        story_err = _stories_structure_error(
            stories_md,
            hashtag_min=hashtag_min,
            hashtag_max=hashtag_max,
        )
        if story_err:
            raise RuntimeError(
                f"Stories output invalid after retry (initial: {reason}; retry: {story_err})"
            )
        month_err = _stories_month_calendar_alignment_error(stories_md, pack_start_date or "")
        if month_err:
            raise RuntimeError(
                f"Stories output invalid after retry (initial: {reason}; retry: {month_err})"
            )
        framing_err = _stories_month_future_framing_error(stories_md, pack_start_date or "")
        if framing_err:
            raise RuntimeError(
                f"Stories output invalid after retry (initial: {reason}; retry: {framing_err})"
            )
        return stories_md

    def _generate_stories(
        self,
        intake: Dict[str, Any],
        is_subscription_variety: bool = False,
        pack_start_date: Optional[str] = None,
        strict_note: Optional[str] = None,
    ) -> str:
        """Generate 30 one-line Story prompts for Instagram/Facebook.

        Stories use the SAME before/during/after key-date phasing as captions:
        pre-launch (days 1 to key_date-1), launch day (key_date), post-launch (key_date+1 to 30).
        KEY_DATE_EVENTS and day mapping must be passed when launch_event_description is set.
        """
        lang = (intake.get("caption_language") or "English (UK)").strip()
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["English (UK)"])
        n = _normalize_intake_case
        business = n((intake.get("business_name") or "").strip(), sentence_case=False) or "Client"
        month_year = datetime.utcnow().strftime("%B %Y")
        start_str = (pack_start_date or "").strip() or datetime.utcnow().strftime("%Y-%m-%d")
        date_context = _build_date_context(start_str)
        date_block = ""
        if date_context:
            deadline_block = _build_deadline_alignment_block(start_str)
            story_day_block = _build_stories_posting_day_alignment_block(start_str)
            month_narrative_block = _build_month_narrative_alignment_block(for_stories=True)
            date_block = f"""

DATE_CONTEXT (their 30 days start on a specific date; use when relevant, e.g. weekday/weekend):
{date_context}

{deadline_block}

{story_day_block}

{month_narrative_block}

You may reference the actual day/date where it helps (e.g. Monday tip, weekend post). Use only when natural.
"""
        # Key date phasing: stories must align with launch/event dates (same as captions)
        launch_desc_raw = (intake.get("launch_event_description") or "").strip()
        launch_desc = n(launch_desc_raw, sentence_case=True) if launch_desc_raw else ""
        key_date_block = _build_key_date_events_story_block(start_str, launch_desc_raw, launch_desc)
        variety_note = ""
        if is_subscription_variety:
            variety_note = "\n\nThis client receives packs monthly; vary story types and angles (polls, BTS, tips, testimonials, etc.) so this month feels fresh and not repetitive with previous packs.\n"
        brand_rule = f"""
CRITICAL — Use ONLY this business name when naming the brand in Idea or Suggested wording: "{business}".
Do not invent, substitute, or use example/tagline business names from training (e.g. do not replace the real name with a slogan or another company). You may use "we" / "us" / "our" where natural; if the business name appears, it must be exactly "{business}".
Ground every suggestion in their intake (offer, audience, goal)—not generic industries from examples."""

        facts_g = n((intake.get("facts_guardrails") or "").strip(), sentence_case=True) if (intake.get("facts_guardrails") or "").strip() else ""
        facts_line = f"\n- Facts / constraints: {facts_g}" if facts_g else ""

        strict_block = f"\n\nSTRICT FIX NOTE: {strict_note}\n" if strict_note else ""
        prompt = f"""Generate 30 Story prompts for Instagram/Facebook Stories. One per day (Day 1–30). Each day must have exactly three parts: Idea, Suggested wording, Story hashtags.

Quality bar: Every story set must be as tailored and specific as a premium content strategist would deliver for this exact business—no generic filler, no wrong dates, no off-brand tone. Match the standard of a highly polished 30-day story plan.

{lang_instruction}{_stories_language_user_block(lang)}

INTAKE:
- Business: {business}
- What they offer: {intake.get('offer_one_line', '')}
- Audience: {intake.get('audience', '')}
- Goal: {intake.get('goal', '')}{facts_line}
{date_block}
{key_date_block}
{variety_note}
{brand_rule}

For each day provide: (1) Idea — a short description of the Story concept (5–15 words). (2) Suggested wording: — one sentence or short suggestion for what to say or show (do not wrap in quotation marks). (3) Story hashtags: — 3–5 relevant hashtags. Mix types: behind-the-scenes, tips, questions, polls, product highlights, testimonials, process reveals, day-in-the-life. Variety is key.

Output format — markdown only, one line per day with all three parts on that line:
---
## 30 Story Ideas | {business} | {month_year}

**Day 1:** Idea: [short idea]. Suggested wording: [suggestion, no quotes]. Story hashtags: #tag1 #tag2 #tag3
**Day 2:** Idea: [short idea]. Suggested wording: [suggestion, no quotes]. Story hashtags: #tag1 #tag2 #tag3
...
**Day 30:** Idea: [short idea]. Suggested wording: [suggestion, no quotes]. Story hashtags: #tag1 #tag2 #tag3
---

Use the exact labels "Idea:", "Suggested wording:", and "Story hashtags:" on every line. Do not put quotation marks around the Suggested wording content. Output the complete list only. No preamble.
{strict_block}"""
        try:
            content = chat_completion(
                system=_build_stories_system_prompt(intake, aligned_with_captions=False),
                user=prompt,
                temperature=0.7,
                max_tokens=3500,
            )
            return content if content else ""
        except Exception as e:
            print(f"[CaptionGenerator] Stories generation failed: {e}")
            return ""

    def _generate_stories_aligned(
        self,
        intake: Dict[str, Any],
        captions_md: str,
        is_subscription_variety: bool = False,
        pack_start_date: Optional[str] = None,
        strict_note: Optional[str] = None,
    ) -> str:
        """Generate 30 Story prompts with explicit day-by-day alignment to captions.

        Also receives KEY_DATE_EVENTS and before/during/after phasing (same as captions)
        so Suggested wording uses correct dates, not invented ones."""
        # Extract "## Day N — ..." headings to summarise each day's caption.
        day_summaries: Dict[int, str] = {}
        for line in captions_md.splitlines():
            m = re.match(r"^##\s*Day\s+(\d+)\s*[—\-]\s*(.+)$", line.strip())
            if not m:
                continue
            try:
                day_num = int(m.group(1))
            except ValueError:
                continue
            if 1 <= day_num <= 30:
                day_summaries[day_num] = m.group(2).strip()

        summary_lines = []
        for i in range(1, 31):
            if i in day_summaries:
                summary_lines.append(f"Day {i}: {day_summaries[i]}")

        summaries_block = "\n".join(summary_lines)

        lang = (intake.get("caption_language") or "English (UK)").strip()
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["English (UK)"])
        n = _normalize_intake_case
        business = n((intake.get("business_name") or "").strip(), sentence_case=False) or "Client"
        month_year = datetime.utcnow().strftime("%B %Y")
        start_str = (pack_start_date or "").strip() or datetime.utcnow().strftime("%Y-%m-%d")
        date_context = _build_date_context(start_str)
        date_block = ""
        if date_context:
            deadline_block = _build_deadline_alignment_block(start_str)
            story_day_block = _build_stories_posting_day_alignment_block(start_str)
            month_narrative_block = _build_month_narrative_alignment_block(for_stories=True)
            date_block = f"""

DATE_CONTEXT (their 30 days start on a specific date; use when relevant):
{date_context}

{deadline_block}

{story_day_block}

{month_narrative_block}

You may reference the actual day/date where it helps. Use only when natural.
"""
        # Key date phasing: stories must align with launch/event dates (same as captions)
        launch_desc_raw = (intake.get("launch_event_description") or "").strip()
        launch_desc = n(launch_desc_raw, sentence_case=True) if launch_desc_raw else ""
        key_date_block = _build_key_date_events_story_block(start_str, launch_desc_raw, launch_desc)
        variety_note = ""
        if is_subscription_variety:
            variety_note = "\n\nThis client receives packs monthly; vary story types and angles (polls, BTS, tips, testimonials, etc.) so this month feels fresh and not repetitive with previous packs.\n"

        brand_rule = f"""
CRITICAL — Use ONLY this business name when naming the brand in Idea or Suggested wording: "{business}".
Do not invent, substitute, or use example/tagline business names from training. If the business name appears, it must be exactly "{business}".
Ground every suggestion in their intake and that day's caption theme—not generic industries from examples."""

        facts_g = n((intake.get("facts_guardrails") or "").strip(), sentence_case=True) if (intake.get("facts_guardrails") or "").strip() else ""
        facts_line = f"\n- Facts / constraints: {facts_g}" if facts_g else ""

        strict_block = f"\n\nSTRICT FIX NOTE: {strict_note}\n" if strict_note else ""
        prompt = f"""Generate 30 Story prompts for Instagram/Facebook Stories. One per day (Day 1–30). Each day must have exactly three parts: Idea, Suggested wording, Story hashtags.

Quality bar: Every story set must be as tailored and specific as a premium content strategist would deliver for this exact business—no generic filler, no wrong dates, no off-brand tone. Each day's story must support that day's caption theme.

{lang_instruction}{_stories_language_user_block(lang)}

INTAKE:
- Business: {business}
- What they offer: {intake.get('offer_one_line', '')}
- Audience: {intake.get('audience', '')}
- Goal: {intake.get('goal', '')}{facts_line}
{date_block}
{key_date_block}
{variety_note}
{brand_rule}

Here is the theme or focus for each day's main caption:
{summaries_block}

For each Day N, write a Story prompt that explicitly supports and reinforces that day's caption. Think of it as the visibility layer between posts: behind-the-scenes, polls, quick proof, or micro-examples that keep the message active.

For each day provide: (1) Idea: — short description of the Story concept (5–15 words). (2) Suggested wording: — one sentence or short suggestion for what to say or show (do not wrap in quotation marks). (3) Story hashtags: — 3–5 relevant hashtags. Mix types; variety is key, but always tied to that day's caption theme.

Output format — markdown only, one line per day with all three parts on that line:
---
## 30 Story Ideas | {business} | {month_year}

**Day 1:** Idea: [short idea]. Suggested wording: [suggestion, no quotes]. Story hashtags: #tag1 #tag2 #tag3
**Day 2:** Idea: [short idea]. Suggested wording: [suggestion, no quotes]. Story hashtags: #tag1 #tag2 #tag3
...
**Day 30:** Idea: [short idea]. Suggested wording: [suggestion, no quotes]. Story hashtags: #tag1 #tag2 #tag3
---

Use the exact labels "Idea:", "Suggested wording:", and "Story hashtags:" on every line. Do not put quotation marks around the Suggested wording content. Output the complete list only. No preamble.
{strict_block}"""

        try:
            content = chat_completion(
                system=_build_stories_system_prompt(intake, aligned_with_captions=True),
                user=prompt,
                temperature=0.7,
                max_tokens=3500,
            )
            return content if content else ""
        except Exception as e:
            print(f"[CaptionGenerator] Aligned stories generation failed: {e}")
            return ""
