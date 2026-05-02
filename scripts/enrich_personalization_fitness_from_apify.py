#!/usr/bin/env python3
"""
Rewrite personalization_line for fitness outreach using Maps category data.

Default: rule-based lines (no API) from categoryName / categories/* joined on website.

With --use-ai: one cold-email icebreaker per row via services.ai_provider.chat_completion
(same stack as captions: AI_PROVIDER=anthropic uses Claude + ANTHROPIC_API_KEY;
AI_PROVIDER=openai or unset uses OpenAI + OPENAI_API_KEY — see config.py / .env.example).

Examples:
  python scripts/enrich_personalization_fitness_from_apify.py \\
    exports/SMARTLEAD_IMPORT_FITNESS_BRISTOL_with_email_only.csv \\
    --apify-csv "/path/to/Gyms Bristol_enriched.csv" \\
    --out exports/SMARTLEAD_IMPORT_FITNESS_BRISTOL_personalized.csv

  python scripts/enrich_personalization_fitness_from_apify.py ... --use-ai \\
    --out exports/SMARTLEAD_IMPORT_FITNESS_BRISTOL_personalized_ai.csv

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


def _personalization(name: str, city: str, blob: str) -> str:
    n = (name or "").strip()
    c = (city or "Bristol").strip() or "Bristol"
    if "crossfit" in blob:
        return (
            f"Saw {n} in {c} — CrossFit boxes that post consistently around timetables "
            f"and member wins usually fill trial spots faster than sporadic drops."
        )
    if "yoga" in blob or "pilates" in blob:
        return (
            f"Saw {n} in {c} — studios like yours tend to grow faster when social posts "
            f"match class rhythms (timetables, new teachers, short reels) instead of generic filler."
        )
    if "personal" in blob or "trainer" in blob:
        return (
            f"Saw {n} in {c} — PT-led brands often win more enquiries when posts reflect "
            f"client outcomes and simple offers, not just motivation quotes."
        )
    if "gym" in blob or "fitness" in blob:
        return (
            f"Saw {n} in {c} — gyms that keep posts tied to timetables, trainers, and "
            f"member stories usually see steadier trial traffic than occasional promos."
        )
    return (
        f"Saw {n} in {c} — fitness brands that post with a clear weekly rhythm "
        f"(classes, coaches, offers) tend to convert local searches better than ad-hoc updates."
    )


_AI_SYSTEM = """You write one opening icebreaker sentence for a cold B2B email. The product is Lumo — done-for-you Instagram caption packs for busy local businesses.

Rules:
- British English; warm and professional; not gushing, not fake-intimate.
- Exactly one sentence. No greeting (no "Hi" or name at the start) — the email template adds that.
- Use the business name naturally. You may mention the city once if it reads smoothly.
- Only use the facts provided (name, city, niche, website, Google Maps categories). Do not invent review scores, awards, or specific things you have not been told about their marketing.
- Angle: light, credible nod to their category (classes, timetables, coaches, consistency of social posts) without pretending you audited their feed.
- Aim under 220 characters. No hashtags, no bullet points, no markdown."""


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
        system=_AI_SYSTEM,
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
    ap.add_argument("smartlead_csv", help="Smartlead CSV with website + business_name + city")
    ap.add_argument("--apify-csv", required=True, help="Apify Maps export (enriched or raw)")
    ap.add_argument("--out", required=True, help="Output CSV path")
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
            try:
                line = _ai_personalization(
                    business_name=r.get("business_name", ""),
                    city=r.get("city", ""),
                    niche=r.get("niche", ""),
                    website=r.get("website", ""),
                    maps_categories=maps_cat,
                )
            except Exception as e:
                blob = by_site_blob.get(w, "")
                extra = f" {r.get('business_name', '')} {_norm_url(r.get('website', ''))}"
                line = _personalization(
                    r.get("business_name", ""),
                    r.get("city", ""),
                    f"{blob} {extra}".lower(),
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
            r["personalization_line"] = _personalization(
                r.get("business_name", ""),
                r.get("city", ""),
                f"{blob} {extra}".lower(),
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
