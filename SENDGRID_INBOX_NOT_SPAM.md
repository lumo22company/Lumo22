# Emails landing in spam — how to improve deliverability

SendGrid is working, but inboxes (Gmail, Outlook, etc.) often put mail in spam when the **sending domain** isn’t authenticated. Fixing that is the main way to get emails into the inbox.

---

## 1. Authenticate your domain in SendGrid (most important)

This tells receiving servers that mail from **@lumo22.com** is legitimate.

1. Go to **SendGrid** → **Settings** → **Sender Authentication** (or **Authenticate Your Domain**).
2. Choose **Domain Authentication** (not only Single Sender).
3. Enter your domain: **lumo22.com** (or the domain you use in `FROM_EMAIL`).
4. SendGrid will show you **DNS records** to add (usually 3 CNAME records).
5. In your **domain registrar** or **DNS host** (where lumo22.com is managed), add those CNAME records exactly as SendGrid shows.
6. Back in SendGrid, click **Verify**. It can take a few minutes to a few hours for DNS to update.

Once verified, mail from **hello@lumo22.com** is signed (DKIM) and aligned with your domain (SPF), so inboxes are much more likely to deliver it to the inbox instead of spam.

---

## 2. Ask customers to add you to contacts (short-term)

Until domain authentication is in place, you can say in the first email or on the thank-you page:

- “Add **hello@lumo22.com** to your contacts so our follow-up emails land in your inbox.”

That helps for that specific address.

---

## 3. Keep subject and content neutral

You’re already doing this: clear, professional subject lines and no spammy language. Avoid ALL CAPS, excessive punctuation, or words like “FREE”, “ACT NOW”, etc. in captions emails.

---

## 4. Check SendGrid Activity

In **SendGrid** → **Activity**, check whether messages show as **Delivered** or **Deferred/Bounced**. If they’re delivered but still in spam, it’s almost always a reputation/authentication issue — domain authentication (step 1) is the fix.

---

**Summary:** Set up **Domain Authentication** in SendGrid for **lumo22.com** and add the DNS records they give you. After verification, the intake and delivery emails should land in the inbox more often.
