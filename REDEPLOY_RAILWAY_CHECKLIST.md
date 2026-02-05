# Railway redeploy checklist (Chat £59 & correct links)

After pushing code changes, use this so the **live** site shows £59 for Chat Assistant and the correct Stripe links.

## 1. Set variables on Railway

1. Open **[Railway](https://railway.app)** → your project → the **Lumo 22** service.
2. Go to **Variables**.
3. Ensure **`CHAT_PAYMENT_LINK`** is set to your £59 Chat Assistant payment link, e.g.  
   `https://buy.stripe.com/test_eVq8wOgro1it2H22o06Vq0i`  
   (Use your live link when you go live.)
4. Save. Railway will redeploy when you change variables.

## 2. Deploy latest code

- **If you use GitHub + Railway:** Push your latest commit to the branch Railway watches (e.g. `main`). Railway will build and deploy.
- **If you use Railway CLI:** From the project folder run  
  `railway up --service "Lumo 22"`

## 3. Confirm after deploy

- **Plans:** [your-app.up.railway.app/plans](https://lumo-22-production.up.railway.app/plans) — Chat Assistant should show **£59** and “Get chat only” should use `CHAT_PAYMENT_LINK`.
- **Website Chat:** [/website-chat](https://lumo-22-production.up.railway.app/website-chat) — **£59/month** and the same link.
- **Activate:** [/activate](https://lumo-22-production.up.railway.app/activate) — “Add Chat Assistant (+£59)” in the add-on section.

If you still see £49 or an old Stripe link, the deploy may be from an old commit — trigger a fresh deploy from the latest commit.
