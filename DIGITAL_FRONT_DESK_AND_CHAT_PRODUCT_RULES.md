# Digital Front Desk, Chat Widget & Bundles — Product Rules

## Product structure (enforced in copy and UX)

- **Digital Front Desk (core)** = email receptionist only. No website chat included in any plan.
- **Website Chat Widget** = separate add-on or included in bundles. Same receptionist (tone, context). Requires its own setup (embed code, domain, behaviour). **Requires Digital Front Desk to be active** (dependency).
- **Bundles** = Digital Front Desk + Website Chat. Positioned as: *"One receptionist across email and your website."* Primary way to get chat without buying add-on separately.

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
