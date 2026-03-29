#!/usr/bin/env python3
"""
Print URLs and sample intake for manual QA: captions + stories, non-English (French).

Usage:
  python3 scripts/product_test_fr_captions_and_stories.py

Open the printed URLs in YOUR browser (logged in). Complete Stripe there — Cursor’s browser
uses a separate session and cannot use your account card.

The sample business is fictional — replace if you prefer.
"""
from urllib.parse import urlencode

BASE = "https://www.lumo22.com"

# Prefills: 1 platform, Instagram & Facebook, Story Ideas add-on, scroll to pricing
params = {
    "platforms": "1",
    "selected": "Instagram & Facebook",
    "stories": "1",
}
pricing_url = f"{BASE}/captions?{urlencode(params)}#pricing"

# Skips product page: straight to checkout (terms modal → then Stripe). Optional business name.
checkout_params = dict(params)
checkout_business = "Atelier Lumière Bordeaux"
checkout_params["business_name"] = checkout_business
checkout_url = f"{BASE}/captions-checkout?{urlencode(checkout_params)}"

print("=== Product test: French captions + Story Ideas ===\n")
print("1a) Product page (pick one-off or sub, then checkout):\n")
print(f"   {pricing_url}\n")
print("1b) Or open checkout directly (same basket: IG+FB + Story Ideas):\n")
print(f"   {checkout_url}\n")
print("2) Read terms in modal → I agree → Stripe (complete payment in your browser).\n")
print("3) On the intake form, set Language to: French\n")
print("4) Paste or adapt this fictional business (all fields should stay coherent in French):\n")
print("---")
SAMPLE = """
Business name: Atelier Lumière Bordeaux
Business type: Studio créatif / services
What they offer (one sentence): Séances photo portrait et branding pour indépendants et petites marques à Bordeaux.
Operating hours: Lun–Ven 9h–18h sur rendez-vous
Primary audience: Entrepreneurs, coachs et marques locales qui veulent des visuels sobres et professionnels
Consumer age range: 28–55 ans
What audience cares about: authenticité, cohérence visuelle, peu de blabla
What they usually talk about: coulisses des shootings, conseils lumière, avant/après
Voice / tone to use: chaleureux, précis, jamais survendu
Words / style to avoid: hustle, mindset, exploser les résultats
Platform(s): (should match checkout — Instagram & Facebook)
Goal for the month: plus de demandes de devis qualifiées via DM et lien en bio
Caption language: French
(Optional) Key date: leave blank or add a plausible French event line for testing phasing
"""
print(SAMPLE.strip())
print("---\n")
print("5) After delivery, verify both PDFs: caption bodies and story Idea/Suggested wording are French,")
print("   and INTAKE SUMMARY shows Language: French.\n")
