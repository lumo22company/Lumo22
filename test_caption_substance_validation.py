#!/usr/bin/env python3
"""Non-TikTok captions must be substantive (min length + multiple sentences)."""

from services.caption_generator import _chunk_structure_error


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
