#!/usr/bin/env python3
"""Non-TikTok captions must be substantive (min length + multiple sentences)."""

from services.caption_generator import (
    _calendar_weekday_alignment_error,
    _caption_month_calendar_alignment_error,
    _chunk_structure_error,
    _rough_sentence_count,
    _stories_month_calendar_alignment_error,
    _stories_month_future_framing_error,
)
from services.caption_pdf import pack_month_range_label


def _long_two_sentences():
    return (
        "Cap Ferrat Villas curates waterfront homes on the Côte d'Azur with private hosts and concierge-led stays. "
        "Guests arrive to a fully prepared home, local recommendations, and a team that handles the details before you ask."
    )


def test_instagram_facebook_one_liner_fails():
    content = """
## Day 1 — AUTHORITY
**Platform:** Instagram & Facebook
**Caption:** That's what sets Cap Ferrat Villas apart.
**Hashtags:** #LuxuryVillas #CôtedAzur #VillaLife #CapFerrat #LuxuryTravel #VillaRental #FrenchRiviera #ExclusiveGetaway
""".strip()
    err = _chunk_structure_error(
        content=content,
        day_start=1,
        day_end=1,
        expected_platform_count=1,
        expected_platform_labels=["Instagram & Facebook"],
        include_hashtags=True,
        hashtag_min=3,
        hashtag_max=10,
    )
    assert err is not None
    assert "too short" in err.lower() or "sentences" in err.lower()


def test_instagram_facebook_substantive_passes():
    body = _long_two_sentences()
    assert len(body) >= 200
    content = f"""
## Day 1 — AUTHORITY
**Platform:** Instagram & Facebook
**Caption:** {body}

**Hashtags:** #LuxuryVillas #CôtedAzur #VillaLife #CapFerrat #LuxuryTravel #VillaRental #FrenchRiviera #ExclusiveGetaway
""".strip()
    err = _chunk_structure_error(
        content=content,
        day_start=1,
        day_end=1,
        expected_platform_count=1,
        expected_platform_labels=["Instagram & Facebook"],
        include_hashtags=True,
        hashtag_min=3,
        hashtag_max=10,
    )
    assert err is None


def test_two_short_sentences_under_200_chars_fail():
    content = """
## Day 1 — AUTHORITY
**Platform:** Instagram & Facebook
**Caption:** Short one. Short two.
**Hashtags:** #LuxuryVillas #CôtedAzur #VillaLife #CapFerrat #LuxuryTravel #VillaRental #FrenchRiviera #ExclusiveGetaway
""".strip()
    err = _chunk_structure_error(
        content=content,
        day_start=1,
        day_end=1,
        expected_platform_count=1,
        expected_platform_labels=["Instagram & Facebook"],
        include_hashtags=True,
        hashtag_min=3,
        hashtag_max=10,
    )
    assert err is not None
    assert "too short" in err.lower()


def _vary_mode_one_sentence_body():
    """Single sentence, >=125 chars, substantive."""
    return (
        "Cap Ferrat Villas curates waterfront homes on the Côte d'Azur with private hosts and concierge-led stays "
        "so every guest walks into a fully prepared home without lifting a finger."
    )


def test_vary_ig_fb_one_substantive_sentence_passes():
    body = _vary_mode_one_sentence_body()
    assert _rough_sentence_count(body) == 1
    assert len(body) >= 125
    content = f"""
## Day 1 — AUTHORITY
**Platform:** Instagram & Facebook
**Caption:** {body}

**Hashtags:** #LuxuryVillas #CôtedAzur #VillaLife #CapFerrat #LuxuryTravel #VillaRental #FrenchRiviera #ExclusiveGetaway
""".strip()
    err = _chunk_structure_error(
        content=content,
        day_start=1,
        day_end=1,
        expected_platform_count=1,
        expected_platform_labels=["Instagram & Facebook"],
        include_hashtags=True,
        hashtag_min=3,
        hashtag_max=10,
        vary_ig_fb_caption_length=True,
    )
    assert err is None


def test_vary_ig_fb_single_sentence_under_125_chars_fails():
    # One sentence, under 125 chars — vary-mode still requires more substance for single-sentence posts
    body = "Cap Ferrat Villas offers curated stays on the French Riviera with concierge support for every booking detail"
    assert _rough_sentence_count(body) == 1
    assert len(body) < 125
    content = f"""
## Day 1 — AUTHORITY
**Platform:** Instagram & Facebook
**Caption:** {body}
**Hashtags:** #LuxuryVillas #CôtedAzur #VillaLife #CapFerrat #LuxuryTravel #VillaRental #FrenchRiviera #ExclusiveGetaway
""".strip()
    err = _chunk_structure_error(
        content=content,
        day_start=1,
        day_end=1,
        expected_platform_count=1,
        expected_platform_labels=["Instagram & Facebook"],
        include_hashtags=True,
        hashtag_min=3,
        hashtag_max=10,
        vary_ig_fb_caption_length=True,
    )
    assert err is not None
    assert "125" in err or "substantive" in err.lower()


def test_vary_ig_fb_two_short_sentences_over_100_chars_passes():
    body = (
        "Cap Ferrat Villas handles every arrival detail before you land. "
        "Ask about our spring availability on the waterfront."
    )
    assert len(body) >= 100
    content = f"""
## Day 1 — AUTHORITY
**Platform:** Instagram & Facebook
**Caption:** {body}

**Hashtags:** #LuxuryVillas #CôtedAzur #VillaLife #CapFerrat #LuxuryTravel #VillaRental #FrenchRiviera #ExclusiveGetaway
""".strip()
    err = _chunk_structure_error(
        content=content,
        day_start=1,
        day_end=1,
        expected_platform_count=1,
        expected_platform_labels=["Instagram & Facebook"],
        include_hashtags=True,
        hashtag_min=3,
        hashtag_max=10,
        vary_ig_fb_caption_length=True,
    )
    assert err is None


def _engagement_body_a():
    return (
        "What brought you to yoga? Was it a recommendation from a friend, a moment when your body asked for gentler movement, "
        "or simple curiosity? We'd love to hear your story. Drop a comment below—let's celebrate what drew each of us to the mat. "
        "Our studio welcomes every answer."
    )


def _engagement_body_b():
    return (
        "What brought you to yoga? Was it a recommendation from a friend, a desire to move more gently, or something else entirely? "
        "We'd love to hear your story. Drop a comment below. "
        "Sharing your path helps others feel less alone."
    )


def test_engagement_same_hook_across_days_fails():
    """Stale duplicate 'what brought you' / same friend line across two Engagement days should fail validation."""
    a, b = _engagement_body_a(), _engagement_body_b()
    assert len(a) >= 200 and len(b) >= 200
    content = f"""
## Day 4 — Engagement
**Platform:** Instagram & Facebook
**Caption:** {a}
**Hashtags:** #YogaCommunity #YogaStories #YogaJourney #MindfulMovement #WellnessOver50 #YogaOver50 #CommunityEngagement

## Day 5 — Engagement
**Platform:** Instagram & Facebook
**Caption:** {b}
**Hashtags:** #YogaStories #CommunityChat #YogaJourney #WomenOver50 #ShareYourStory
""".strip()
    err = _chunk_structure_error(
        content=content,
        day_start=4,
        day_end=5,
        expected_platform_count=1,
        expected_platform_labels=["Instagram & Facebook"],
        include_hashtags=True,
        hashtag_min=3,
        hashtag_max=10,
    )
    assert err is not None
    assert "engagement" in err.lower() or "near-duplicate" in err.lower()


def test_engagement_two_distinct_days_passes():
    body1 = (
        "Myth or fact: you need to be flexible before your first yoga class. "
        "We hear this every week—and our teachers love unpacking it. "
        "Vote in the comments: myth or fact? We'll share the gentle truth in stories."
    )
    body2 = (
        "When was the last time you finished a class and felt genuinely lighter—not just in your body, but in your head? "
        "We are collecting one-word answers in the comments for a studio wall. "
        "No pressure to share more than a single word."
    )
    assert len(body1) >= 200 and len(body2) >= 200
    content = f"""
## Day 4 — Engagement
**Platform:** Instagram & Facebook
**Caption:** {body1}
**Hashtags:** #YogaCommunity #YogaStories #YogaJourney #MindfulMovement #WellnessOver50 #YogaOver50 #CommunityEngagement

## Day 5 — Engagement
**Platform:** Instagram & Facebook
**Caption:** {body2}
**Hashtags:** #YogaStories #CommunityChat #YogaJourney #WomenOver50 #ShareYourStory
""".strip()
    err = _chunk_structure_error(
        content=content,
        day_start=4,
        day_end=5,
        expected_platform_count=1,
        expected_platform_labels=["Instagram & Facebook"],
        include_hashtags=True,
        hashtag_min=3,
        hashtag_max=10,
    )
    assert err is None


def test_calendar_rejects_this_friday_on_friday_post():
    """Same-day class on a Friday must not use 'This Friday morning' (SAME_POST_DAY_AS_EVENT)."""
    # Pack start 2026-04-09 → Day 16 = Fri 24 Apr 2026
    md = """
## Day 16 — Soft Promotion
**Platform:** Instagram & Facebook
**Caption:** This Friday morning, join us for a free class. Bring yourself, nothing else. We'll handle the rest. Extra text here so the caption meets minimum length checks elsewhere in the pipeline for substantive delivery quality standards.
**Hashtags:** #FreeYogaClass #YogaForWomen #WomenOver50 #JoinOurCommunity #YogaInvitation
""".strip()
    err = _calendar_weekday_alignment_error(md, "2026-04-09")
    assert err is not None
    assert "day 16" in err.lower() or "friday" in err.lower()


def test_calendar_allows_this_friday_from_thursday_post():
    """Thursday post may use 'this Friday' for tomorrow's Friday class."""
    md = """
## Day 1 — Soft Promotion
**Platform:** Instagram & Facebook
**Caption:** We're opening a few spots for this Friday morning. If you've been curious about our gentle flow, this is a low-pressure way to try it. Book via the link in bio — we cap the room so everyone has space. Questions welcome in the comments.
**Hashtags:** #FreeYogaClass #YogaForWomen #WomenOver50 #JoinOurCommunity #YogaInvitation
""".strip()
    err = _calendar_weekday_alignment_error(md, "2026-04-09")
    assert err is None


def test_pack_month_range_label_spans_two_months():
    assert pack_month_range_label("2026-04-09") == "April – May 2026"


def test_pack_month_range_label_single_month():
    assert pack_month_range_label("2026-03-01") == "March 2026"


def test_month_alignment_rejects_april_wrap_on_may_day():
    md = """
## Day 30 — Brand Personality
**Platform:** Instagram & Facebook
**Caption:** As we close out April, we're grateful for everyone who's walked through our doors. Thank you for being part of our studio. We mean every word and look forward to seeing you on the mat again soon this season.
**Hashtags:** #a #b #c #d #e
""".strip()
    err = _caption_month_calendar_alignment_error(md, "2026-04-09")
    assert err is not None
    assert "day 30" in err.lower()


def test_month_alignment_allows_april_wrap_on_april_day():
    md = """
## Day 20 — Brand Personality
**Platform:** Instagram & Facebook
**Caption:** As we close out April, we're grateful for everyone who's walked through our doors this month. Thank you for being part of our studio community and we will see you on the mat.
**Hashtags:** #a #b #c #d #e
""".strip()
    err = _caption_month_calendar_alignment_error(md, "2026-04-09")
    assert err is None


def test_month_alignment_rejects_april_has_been_on_may_caption_day():
    """Phrases like 'April has been incredible' on a May calendar day must fail validation."""
    md = """
## Day 30 — Brand Personality
**Platform:** Instagram & Facebook
**Caption:** Friday wrap: April has been incredible. Here is to May and what is next.
**Hashtags:** #a #b #c #d #e
""".strip()
    err = _caption_month_calendar_alignment_error(md, "2026-04-09")
    assert err is not None
    assert "day 30" in err.lower()


def test_stories_month_alignment_rejects_april_wrap_on_may_day():
    stories = """
**Day 30:** Idea: Friday thank-you. Suggested wording: Friday wrap: April has been incredible — here is to May. Story hashtags: #a #b #c
""".strip()
    err = _stories_month_calendar_alignment_error(stories, "2026-04-09")
    assert err is not None
    assert "story day 30" in err.lower()


def test_stories_month_alignment_allows_look_back_april_on_may_day():
    """Explicit look-back framing can name April on a May posting day."""
    stories = """
**Day 30:** Idea: Friday thank-you. Suggested wording: Looking back at April — thank you. Here is to May. Story hashtags: #a #b #c
""".strip()
    err = _stories_month_calendar_alignment_error(stories, "2026-04-09")
    assert err is None


def test_stories_reject_may_is_coming_on_may_calendar_day():
    """Day 23 = 1 May 2026 when pack starts 9 Apr — 'May is coming' is wrong on 1 May."""
    stories = """
**Day 23:** Idea: Friday teaser. Suggested wording: May is coming, and we have new menu items. Story hashtags: #a #b #c
""".strip()
    err = _stories_month_future_framing_error(stories, "2026-04-09")
    assert err is not None
    assert "day 23" in err.lower()


def test_stories_allow_may_is_coming_before_may():
    """Teasing May from April is OK."""
    stories = """
**Day 22:** Idea: Teaser. Suggested wording: May is coming — get ready. Story hashtags: #a #b #c
""".strip()
    err = _stories_month_future_framing_error(stories, "2026-04-09")
    assert err is None
