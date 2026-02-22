# Website Setup Guide - Lumo 22

The Lumo 22 app includes a full site with landing page, product pages, and pricing.

---

## Option 1: Use the Built-in App (Current Setup)

The app serves:
- **Landing:** `/` — Hero, split panels (Digital Front Desk + Captions)
- **Pricing:** `/digital-front-desk#pricing` — Starter, Growth, Pro with Stripe links
- **Activate:** `/activate` — Plan selection, T&Cs, checkout
- **Captions:** `/captions` — 30 Days Captions product
- **Website Chat:** `/website-chat` — Chat Assistant £59

### Stripe Links

Payment links are configured in Railway (or `.env`):
- `ACTIVATION_LINK_STARTER`, `ACTIVATION_LINK_STANDARD`, `ACTIVATION_LINK_PREMIUM`
- `CHAT_PAYMENT_LINK` — standalone chat £59
- Bundle links: `ACTIVATION_LINK_STARTER_BUNDLE`, etc.

### Success URLs

In Stripe, set each payment link's Success URL:
- Front Desk / Bundles: `{BASE_URL}/activate-success`
- Chat only: `{BASE_URL}/website-chat-success`
- Captions: `{BASE_URL}/captions-thank-you`

---

## Option 2: Use a Website Builder (No Code)

### Carrd (Recommended - Free)

1. Go to https://carrd.co
2. Sign up (free)
3. Choose "Blank" template
4. Add sections:
   - **Header:** "AI Receptionist - Replace Your Receptionist for Under 10% of the Cost"
   - **Comparison:** "A receptionist costs £1,200+/month. Our AI works 24/7 for £149/month."
   - **Pricing Cards:** Add 3 cards with your tiers
   - **Buttons:** Link each to your Stripe payment links
5. Publish (get free `.carrd.co` URL or use custom domain)

### Notion (Simple)

1. Create a new Notion page
2. Add your pricing tiers
3. Add buttons linking to Stripe
4. Click "Share" → "Publish to web"
5. Get public URL

---

## Option 3: Customize the HTML

The HTML file I created includes:
- ✅ Professional design
- ✅ Mobile responsive
- ✅ Three pricing tiers
- ✅ "Most Popular" badge on Standard
- ✅ Comparison messaging
- ✅ Guarantee text

**To customize:**
- Change colors: Edit the `#667eea` color codes
- Change text: Edit the HTML content
- Add logo: Add `<img>` tag in header
- Add testimonials: Add new section

---

## Quick Setup Checklist

- [ ] Edit `pricing-page.html` with your Stripe links
- [ ] Choose hosting method (Netlify/Carrd/etc.)
- [ ] Upload/publish your page
- [ ] Test all three payment links
- [ ] Update your AI email to link to pricing page (not direct Stripe)
- [ ] Share your pricing page URL

---

## What Your AI Email Should Say Now

Instead of:
```
Activate here: https://buy.stripe.com/xxxxx
```

Use:
```
Choose your plan and activate here:
https://your-pricing-page.com

No calls needed. Just select your tier and go live.
```

---

## Pro Tips

1. **Start Simple:** Use the HTML file I created - it's ready to go
2. **Free Hosting:** Netlify Drop is the fastest (drag & drop)
3. **Test First:** Make sure all three Stripe links work before going live
4. **Track Clicks:** You can add Google Analytics later if you want
5. **A/B Test:** Try different messaging once you have traffic

---

## Next Steps

1. ✅ Edit the HTML file with your Stripe links
2. ✅ Host it (Netlify/Carrd/etc.)
3. ✅ Test all payment links
4. ✅ Update your AI email to link to pricing page
5. ✅ You're ready to accept payments!

**You now have a professional pricing page!** 🎉
