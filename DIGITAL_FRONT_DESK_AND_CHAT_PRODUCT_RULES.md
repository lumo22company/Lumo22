# Digital Front Desk, Chat Widget & Bundles — Product Rules

## Product structure (enforced in copy and UX)

Users can choose one of three options:

1. **Chat only** — Standalone Website Chat Widget (£59/month). Chat on your site only; no email inbox. Can add email receptionist later or move to a bundle.
2. **Email only** — Digital Front Desk (Starter £79, Standard £149, Premium £299). Email receptionist only; no chat included in the plan. Can add chat as add-on or get a bundle.
3. **Bundle** — Digital Front Desk + Website Chat. One receptionist across email and your website. Add chat to any email plan, or purchase as a bundle.

- **Digital Front Desk (core)** = email receptionist only. No website chat included in any plan.
- **Website Chat Widget** = standalone product (chat only) OR add-on to an email plan OR included in bundles. Same receptionist (tone, context). Own setup (embed code, domain, behaviour).
- **Bundles** = Digital Front Desk + Website Chat. Positioned as: *"One receptionist across email and your website."*

## Marketing and copy (implemented)

- `/digital-front-desk` and `/plans`: All plans described as email-only. "Website chat" removed from Standard and Premium. CTAs: "Add Website Chat" / "Available in bundles".
- No plan implies chat unless it is explicitly a bundle. Language is consistent across hero, features, tables, and footnotes.

## Intake / setup flows (keep separate)

- **Digital Front Desk intake:** Email routing, booking link, business description, tone/services. No merge with chat form.
- **Website Chat intake:** Business name, domain(s), lead email, booking link, chat behaviour (e.g. booking prompts). Separate form and flow.

## Technical enforcement (TODO)

- **Chat widget activation:** Chat widget should not be activated unless Digital Front Desk is active (or customer is on a bundle that includes both). Current implementation allows standalone chat purchase; add a check at setup/embed generation or at payment to enforce: *chat requires active Front Desk or bundle*.
- **Bundles:** When a bundle product is purchased, automatically unlock chat widget setup and embed code generation (same as add-on flow, but gated by bundle entitlement instead of separate chat purchase).
- **Backend:** Persist bundle vs add-on entitlement so embed code and chat API can verify: customer has either (a) active Front Desk + chat add-on, or (b) bundle that includes chat.
