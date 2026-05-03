#!/usr/bin/env python3
"""
Rewrite personalization_line for Smartlead outreach.

Default: rule-based lines. If --apify-csv is set, join on website and use Google Maps
categories for fitness / studio / gym buckets. If --apify-csv is omitted, buckets use
the CSV `niche` column plus business name / domain hints (beauty, interior, fitness, generic).

With --use-ai: one cold-email icebreaker per row via services.ai_provider.chat_completion
(Anthropic or OpenAI per config.py / .env). Use --vertical auto|fitness|general so the
prompt matches the list (auto picks from niche + Maps categories).

Examples:
  python scripts/enrich_personalization_fitness_from_apify.py \\
    exports/SMARTLEAD_IMPORT_FITNESS_BRISTOL_with_email_only.csv \\
    --apify-csv "/path/to/Gyms Bristol_enriched.csv" \\
    --out exports/SMARTLEAD_IMPORT_FITNESS_BRISTOL_personalized.csv

  python scripts/enrich_personalization_fitness_from_apify.py \\
    exports/smartlead_super_safe_batch_100_merged_emails.csv \\
    --use-ai --vertical general --out exports/smartlead_batch100_personalized_ai.csv

  python scripts/enrich_personalization_fitness_from_apify.py ... --use-ai --dry-run --limit 3
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv

load_dotenv()


def _norm_key(name: str) -> str:
    k = (name or "").lstrip("\ufeff").strip()
    if k.startswith('"') and k.endswith('"') and len(k) >= 2:
        k = k[1:-1]
    return k.strip()


def _norm_url(u: str) -> str:
    u = (u or "").strip().lower().rstrip("/")
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    return u


def _category_blob(row: dict[str, str]) -> str:
    parts = [
        row.get("categoryName", ""),
        row.get("categories/0", ""),
        row.get("categories/1", ""),
    ]
    return " ".join(p for p in parts if p).lower()


def _maps_categories_label(row: dict[str, str]) -> str:
    parts = [
        row.get("categoryName", ""),
        row.get("categories/0", ""),
        row.get("categories/1", ""),
        row.get("categories/2", ""),
    ]
    return "; ".join(p.strip() for p in parts if (p or "").strip()) or "not listed"


def _personalization(name: str, city: str, blob: str, niche: str = "") -> str:
    n = (name or "").strip()
    c = (city or "").strip() or "your city"
    comb = f"{blob} {(niche or '').lower()}"

    if "interior" in comb:
        return (
            f"Saw {n} in {c} — design-led studios that keep Instagram tied to projects and "
            f"process tend to stay top-of-mind when people start planning work at home."
        )
    if any(k in comb for k in ("hair", "beauty", "salon", "nail", "lash", "brow", "spa", "barber")):
        return (
            f"Saw {n} in {c} — salons that align posts with services, offers, and real client outcomes "
            f"usually fill the diary more steadily than occasional generic drops."
        )
    if "crossfit" in comb:
        return (
            f"Saw {n} in {c} — CrossFit boxes that post consistently around timetables "
            f"and member wins usually fill trial spots faster than sporadic drops."
        )
    if "yoga" in comb or "pilates" in comb:
        return (
            f"Saw {n} in {c} — studios like yours tend to grow faster when social posts "
            f"match class rhythms (timetables, new teachers, short reels) instead of generic filler."
        )
    if "personal" in comb or "trainer" in comb:
        return (
            f"Saw {n} in {c} — PT-led brands often win more enquiries when posts reflect "
            f"client outcomes and simple offers, not just motivation quotes."
        )
    if "gym" in comb or "fitness" in comb:
        return (
            f"Saw {n} in {c} — gyms that keep posts tied to timetables, trainers, and "
            f"member stories usually see steadier trial traffic than occasional promos."
        )
    if any(k in comb for k in ("restaurant", "cafe", "coffee", "food")):
        return (
            f"Saw {n} in {c} — indies that post menus, specials, and regularity on Instagram "
            f"often win more walk-ins than accounts that go quiet for weeks."
        )
    return (
        f"Saw {n} in {c} — local brands that keep social content aligned with what they sell "
        f"usually get more inbound than one-off bursts."
    )


_AI_RULES_TAIL = """
- Do not mention the product name, "captions", "Lumo", or "we handle" in this sentence — opener is empathy and their world only; the email body sells the offer.
- British English; warm and professional; not gushing, not fake-intimate.
- Exactly one sentence. No greeting (no "Hi" or name at the start) — the email template adds that.
- Use the business name naturally. You may mention the city once if it reads smoothly.
- Only use the facts provided (name, city, niche label, website, Google Maps categories). Do not invent review scores, awards, or specific claims about their marketing you cannot verify.
- Aim under 220 characters. No hashtags, no bullet points, no markdown."""

_AI_SYSTEM_FITNESS = (
    "You write one opening icebreaker sentence for a cold B2B email to a fitness or movement business.\n"
    "Angle: timetables, classes, coaches, member stories, consistency of posts — without pretending you audited their feed."
    + _AI_RULES_TAIL
)

_AI_SYSTEM_GENERAL = (
    "You write one opening icebreaker sentence for a cold B2B email to a local service or retail business.\n"
    "Angle: light nod to their industry from the niche label (services, portfolio, bookings, local demand) — credible, not stalker-y."
    + _AI_RULES_TAIL
)


def _ai_system_for_row(vertical: str, niche: str, maps_categories: str) -> str:
    if vertical == "fitness":
        return _AI_SYSTEM_FITNESS
    if vertical == "general":
        return _AI_SYSTEM_GENERAL
    blob = f"{(niche or '').lower()} {(maps_categories or '').lower()}"
    if any(
        x in blob
        for x in (
            "gym",
            "fitness",
            "crossfit",
            "yoga",
            "pilates",
            "personal trainer",
            "pilates studio",
            "yoga studio",
        )
    ):
        return _AI_SYSTEM_FITNESS
    return _AI_SYSTEM_GENERAL


def _clean_one_sentence(text: str) -> str:
    t = (text or "").strip().replace("\n", " ")
    t = re.sub(r'^["\']|["\']$', "", t).strip()
    m = re.match(r"^(.+?[.!?])(\s|$)", t)
    if m:
        t = m.group(1).strip()
    if len(t) > 260:
        t = t[:257].rsplit(" ", 1)[0] + "…"
    return t


def _ai_personalization(
    *,
    business_name: str,
    city: str,
    niche: str,
    website: str,
    maps_categories: str,
    system: str,
) -> str:
    from services.ai_provider import chat_completion

    user = (
        f"Business name: {business_name}\n"
        f"City: {city}\n"
        f"Niche label: {niche}\n"
        f"Website: {website}\n"
        f"Google Maps categories: {maps_categories}\n\n"
        "Write the single icebreaker sentence only. Nothing else."
    )
    raw = chat_completion(
        system=system,
        user=user,
        temperature=0.45,
        max_tokens=120,
    )
    return _clean_one_sentence(raw)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("smartlead_csv", help="Smartlead CSV with website + business_name + city + niche")
    ap.add_argument(
        "--apify-csv",
        default=None,
        help="Optional Apify Maps export joined on website for richer categories",
    )
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument(
        "--vertical",
        choices=("auto", "fitness", "general"),
        default="auto",
        help="AI prompt flavour (auto uses niche + Maps categories)",
    )
    ap.add_argument(
        "--use-ai",
        action="store_true",
        help="Generate lines via AI (Config / .env keys; see services.ai_provider)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="With --use-ai: call API for --limit rows and print lines only; no CSV write",
    )
    ap.add_argument("--limit", type=int, default=0, help="Process at most N rows (0 = all)")
    ap.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="Seconds to sleep between AI calls (rate limits; default 0.25)",
    )
    args = ap.parse_args()

    by_site_blob: dict[str, str] = {}
    by_site_maps_label: dict[str, str] = {}
    if args.apify_csv:
        with open(args.apify_csv, newline="", encoding="utf-8-sig") as f:
            for raw in csv.DictReader(f):
                row = {_norm_key(k): (v or "").strip() for k, v in raw.items()}
                w = _norm_url(row.get("website", ""))
                if not w:
                    continue
                by_site_blob[w] = _category_blob(row)
                by_site_maps_label[w] = _maps_categories_label(row)

    with open(args.smartlead_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("No rows in smartlead csv")
    fields = list(rows[0].keys())

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    if args.use_ai:
        for i, r in enumerate(rows):
            w = _norm_url(r.get("website", ""))
            maps_cat = by_site_maps_label.get(w, "not listed")
            niche = (r.get("niche") or "").strip()
            system = _ai_system_for_row(args.vertical, niche, maps_cat)
            try:
                line = _ai_personalization(
                    business_name=r.get("business_name", ""),
                    city=r.get("city", ""),
                    niche=niche,
                    website=r.get("website", ""),
                    maps_categories=maps_cat,
                    system=system,
                )
            except Exception as e:
                blob = by_site_blob.get(w, "")
                extra = f" {r.get('business_name', '')} {_norm_url(r.get('website', ''))}"
                line = _personalization(
                    r.get("business_name", ""),
                    r.get("city", ""),
                    f"{blob} {extra}".lower(),
                    niche=niche,
                )
                print(f"[warn] row {i + 1} {r.get('business_name', '')!r}: AI failed ({e}); used rule fallback")
            r["personalization_line"] = line
            if args.dry_run:
                print(f"--- {r.get('business_name')} ---\n{line}\n")
            elif args.sleep > 0 and i < len(rows) - 1:
                time.sleep(args.sleep)
        if args.dry_run:
            print(f"Dry-run: {len(rows)} line(s); no file written.")
            return
    else:
        for r in rows:
            w = _norm_url(r.get("website", ""))
            blob = by_site_blob.get(w, "")
            extra = f" {r.get('business_name', '')} {_norm_url(r.get('website', ''))}"
            niche = (r.get("niche") or "").strip()
            r["personalization_line"] = _personalization(
                r.get("business_name", ""),
                r.get("city", ""),
                f"{blob} {extra}".lower(),
                niche=niche,
            )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    mode = "AI" if args.use_ai else "rule-based"
    print(f"Wrote {len(rows)} rows ({mode}) to {out}")


if __name__ == "__main__":
    main()
