# Pricing structure note

## Current pricing

| Option              | Price |
|---------------------|-------|
| Chat Assistant      | £59   |
| Starter (email)     | £79   |
| Starter + chat      | £131  (5% off £138) |
| Standard (email)    | £149  |
| Standard + chat     | £198  (5% off £208) |
| Premium (email)     | £299  |
| Premium + chat      | £340  (5% off £358) |

**Chat Assistant:** £59/month standalone.  
**Bundle = tier + £59, then 5% off the total.** Starter+chat = (79+59)×0.95 = £131, Standard+chat = £198, Premium+chat = £340. To change chat price or discount, update templates, run `scripts/create_chat_single_stripe_link.py` and/or `scripts/create_bundle_stripe_links_discounted.py`, then .env and webhook amounts.
