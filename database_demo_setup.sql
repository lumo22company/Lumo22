-- Digital Front Desk: demo setup for reply-demo@inbound.lumo22.com
-- Run in Supabase SQL Editor (Dashboard → SQL Editor → New query → paste → Run).
-- After this, visitors can email reply-demo@inbound.lumo22.com to see the instant AI reply.
-- Ensure INBOUND_EMAIL_DOMAIN=inbound.lumo22.com in your env (or update the address below).

INSERT INTO front_desk_setups (
  done_token,
  customer_email,
  business_name,
  enquiry_email,
  forwarding_email,
  status,
  product_type,
  auto_reply_enabled,
  booking_link,
  tone,
  opening_hours,
  reply_same_day,
  reply_24h,
  good_lead_rules
) VALUES (
  'demo-token-' || substr(md5(random()::text), 1, 12),
  'demo@lumo22.com',
  'Blossom Beauty',
  'hello@blossombeauty.co.uk',
  'reply-demo@inbound.lumo22.com',
  'connected',
  'front_desk',
  true,
  'https://calendly.com/demo/consultation',
  'friendly_relaxed',
  'Tue–Sat 9am–6pm',
  true,
  true,
  'When they mention a specific treatment, want to book, or ask about availability'
)
ON CONFLICT (forwarding_email)
DO UPDATE SET
  business_name = EXCLUDED.business_name,
  enquiry_email = EXCLUDED.enquiry_email,
  status = EXCLUDED.status,
  product_type = EXCLUDED.product_type,
  auto_reply_enabled = EXCLUDED.auto_reply_enabled,
  booking_link = EXCLUDED.booking_link,
  tone = EXCLUDED.tone,
  opening_hours = EXCLUDED.opening_hours,
  reply_same_day = EXCLUDED.reply_same_day,
  reply_24h = EXCLUDED.reply_24h,
  good_lead_rules = EXCLUDED.good_lead_rules,
  updated_at = NOW();
