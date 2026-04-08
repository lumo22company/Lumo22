#!/usr/bin/env python3
"""Non-TikTok captions must be substantive (min length + multiple sentences)."""

from services.caption_generator import _chunk_structure_error, _rough_sentence_count


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
