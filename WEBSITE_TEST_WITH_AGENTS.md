# Testing the whole website using Agency agents

Use the Cursor rules from [agency-agents](https://github.com/msitarzewski/agency-agents) to test your site and produce an analysis. The agents are in `.cursor/rules/`.

---

## 1. How to invoke an agent in Cursor

- **In Chat:** Type `@` and start typing the agent name (e.g. `@reality-checker`), or say:
  - *"Use the Reality Checker agent to review this codebase for production readiness."*
  - *"Act as the Evidence Collector and run through the manual test checklist."*
- **By name:** Cursor will suggest rules; pick the one you want. The rule file names are the agent slugs (e.g. `reality-checker.mdc`, `evidence-collector.mdc`).

---

## 2. Agents that fit “test whole website + analysis”

| Agent | Use for |
|-------|--------|
| **@reality-checker** | Production readiness, quality gates, release certification. Good for an overall “is this ready to ship?” analysis. |
| **@evidence-collector** | Screenshot-based QA, visual proof, bug documentation. Good for systematic UI/flow testing. |
| **@accessibility-auditor** | WCAG, screen readers, inclusive design. Use for an accessibility pass. |
| **@frontend-developer** | UI implementation, performance, Core Web Vitals. Use for front-end and UX review. |
| **@ux-researcher** | User testing, behaviour, research. Use for UX and flow analysis. |
| **@api-tester** | API validation, integration testing. Use if you want to test backend/API behaviour. |

### Privacy & security (from [agency-agents](https://github.com/msitarzewski/agency-agents))

Add these rule files to `.cursor/rules/` (copy from the repo paths below, using Cursor’s rule format — see the agency README), then `@` them in Chat:

| Agent / rule file (in repo) | Use for |
|-----------------------------|---------|
| **Security Engineer** — `engineering/engineering-security-engineer.md` | Threat model, OWASP-style code review, auth/session/secrets, headers, injection/XSS/CSRF surfaces, webhook hardening. |
| **Threat Detection Engineer** — `engineering/engineering-threat-detection-engineer.md` | Logging, anomaly patterns, abuse/detection angle on public endpoints and cron. |
| **Compliance Auditor** — `specialized/compliance-auditor.md` | Privacy policy vs actual data collection, retention, lawful basis wording (assistive only — not legal advice). |
| **@reality-checker** + **@api-tester** | Already useful for `SECRET_KEY`, security headers, and API/auth behaviour (see `AGENT_TEST_RUN.md`). |

**Important:** Agency agents are **assistive reviews**, not a penetration test, SOC 2 audit, or legal sign-off. Combine with tools (e.g. `pip-audit` / Dependabot, optional OWASP ZAP on staging) and professional review for high-stakes deployments.

**Lumo-focused runbook:** See **`PRIVACY_SECURITY_AGENT_RUN.md`** for copy-paste prompts and app-specific checklist items (Supabase, Stripe webhooks, intake PII, sessions).

---

## 3. Suggested workflow for a full website test + analysis

### Step A – One-shot “full site analysis” (Reality Checker)

In Cursor Chat, reference the agent and your checklist, and ask for an analysis:

```
Use the @reality-checker agent.

Context: This is the Lumo 22 Captions product (Flask app). We have a manual test checklist in MANUAL_TEST_CHECKLIST.md and the codebase in this project.

Please:
1. Review the main user flows (landing → product → checkout → intake → account).
2. Check for production readiness (config, errors, security, performance).
3. Produce a short written analysis with: what’s solid, what’s risky, and what to test manually or fix before go-live.
```

### Step B – Structured testing (Evidence Collector)

Ask for a test plan and evidence-based report:

```
Use the @evidence-collector agent.

We have MANUAL_TEST_CHECKLIST.md. Please:
1. Turn the checklist into a concrete test plan (steps, expected results).
2. List what to verify (screens, links, forms) and what “evidence” to capture (e.g. screenshot of thank-you page, intake form validation).
3. Output a short report template I can fill in when I run the tests (or when you simulate checks from the code).
```

### Step C – Accessibility pass (Accessibility Auditor)

```
Use the @accessibility-auditor agent.

Review our main templates (landing, captions product, checkout, intake, account dashboard) and any key components for:
- WCAG 2.1 AA issues (contrast, focus, labels, structure).
- Screen reader and keyboard usability.
- A short list of fixes and recommendations.
```

### Step D – Front-end and UX (Frontend Developer + UX Researcher)

- **Frontend:** *"Use the @frontend-developer agent to review our landing and captions pages for performance, layout, and best practices. Summarise findings and quick wins."*
- **UX:** *"Use the @ux-researcher agent to review the flows: signup → login → checkout → intake → account. List friction points and 3–5 UX improvements."*

---

## 4. Getting a single “analysis” document

To get one consolidated analysis:

1. Run **Step A** (Reality Checker) and copy the output into a doc (e.g. `WEBSITE_TEST_ANALYSIS.md`).
2. Run **Step B** (Evidence Collector) and add a “Test plan & evidence” section.
3. Run **Step C** (Accessibility Auditor) and add an “Accessibility” section.
4. Optionally run **Step D** and add “Front-end” and “UX” sections.
5. Optionally run **Privacy & security** (see §2 above and `PRIVACY_SECURITY_AGENT_RUN.md`) and add a “Security & privacy” section.

You can then say in a final message:

*"Combine the outputs from the Reality Checker, Evidence Collector, and Accessibility Auditor into one WEBSITE_TEST_ANALYSIS.md with sections: Executive summary, Production readiness, Test plan & evidence, Accessibility, and Recommended next steps."*

(Add **Security & privacy** to that list if you ran those agents.)

---

## 5. Quick start (minimal)

1. Open Cursor Chat in this project.
2. Type: **Use the @reality-checker agent. Review this codebase and MANUAL_TEST_CHECKLIST.md and write a production-readiness and test analysis for the Lumo 22 website.**
3. Use the reply as your first version of the analysis; then add passes with **@evidence-collector** and **@accessibility-auditor** if you want more depth.

---

## 6. Reference

- Manual checklist: `MANUAL_TEST_CHECKLIST.md`
- Privacy & security agent prompts + Lumo checklist: `PRIVACY_SECURITY_AGENT_RUN.md`
- Agent rules: `.cursor/rules/*.mdc` (install agents from the agency repo into this folder)
- Agency repo: https://github.com/msitarzewski/agency-agents
