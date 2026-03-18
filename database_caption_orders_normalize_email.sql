-- One-off: normalize customer_email to lowercase so account dashboard (get_by_customer_email) finds orders.
-- Run once if you have existing orders created before we stored lowercase (e.g. test one-off not showing on account).
-- Safe to run multiple times (idempotent).

UPDATE caption_orders
SET customer_email = LOWER(TRIM(customer_email))
WHERE customer_email IS NOT NULL
  AND customer_email != LOWER(TRIM(customer_email));
