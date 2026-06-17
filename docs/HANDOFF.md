# Kaizen Atlas: Master Handoff for Claude Code

This is the single source of truth for building Kaizen Atlas, the internal P&L dashboard. Everything here was validated against real Stripe, Xero, and Gusto data across January to May 2026 before any code was written. Build against this and you should not need to rediscover anything.

**Kaizen Atlas is a standalone project, completely separate from Kaizen Launch.** Own repo in the kaizen-cc org, own environment, own secrets. Do not import from or reference Launch.

---

## The package

Give Claude Code all of these:

1. **Kaizen_Atlas_HANDOFF.md** (this file) the authoritative spec and rules.
2. **kaizen_atlas_fixtures.json** validated numbers to assert the engine against.
3. **Kaizen_Software_Allocation_Key.md** the locked software-to-team mapping.
4. **Kaizen_PnL_Dashboard_Build_Spec.md** the architectural blueprint.
5. **kaizen_atlas_may_prototype.html** the approved visual target for the UI.
6. **Kaizen_Atlas_ClaudeCode_Kickoff.md** the opening prompt and phase plan.

---

## Environment and secrets

Read-only credentials, stored in the project environment (gitignored .env or a secret manager). Never commit, never log.

- TOGGL_API_TOKEN (obtained; lives here, in the project)
- Stripe, Xero, Gusto credentials, scoped read-only

---

## Data sources and the quirks that cost time to learn

**Stripe (revenue).**
- Operation: GetInvoices. Date filter must be a nested object: `{"created":{"gte":<epoch>,"lt":<epoch>}}`. Bracket-string syntax is silently ignored.
- Amounts are in cents (75000 = $750.00).
- Each line item carries a `parent`: `subscription_item_details` means subscription (MRR), `invoice_item_details` means a manual one-off.
- Recognize MRR by the line item's subscription **period**, not by payment date. This neutralizes late and multi-month catch-up checks.
- A month's paid invoices fit in one page of 100 for this account (80 to 96 per month observed).

**Xero (overhead, software, reconciliation, cost-increase widget).**
- Books are **cash basis**. Critical: on cash basis, Wages & Salaries and Payroll Tax show $0 because salaried wages are booked as journals that do not flow to cash-basis reports. **Labor therefore comes from Gusto, never from the Xero wages line.**
- Software lives in the "Softwares" account. Group transactions by the "Related account" field; spend = negative of Gross.
- The "830 - Contractors" account holds the offshore hourly team AND the photographers ($239k YTD). Reconcile Gusto against this account so no one is counted twice.
- For the cost-increase widget, group by Related account and compare months. Exclude bank/clearing accounts (AMEX, BofA, Stripe USD, PayPal, Gusto Clearing), income (Stripe Income, Services), Owners Draw, and the payroll journal combo lines.

**Gusto (labor actuals, source of truth).** Salaried staff flat monthly; contractors hourly. Allocate to teams and clients by Toggl hours; reconcile totals to Gusto each run.

**Toggl (labor allocation).** Reports API with the token. Hours per member, per client, per month. This is the unlock that turns per-client cost and employee-level labor real.

---

## Revenue engine (validated)

**Count an invoice as revenue if** Stripe marks it paid OR the customer is on the off-Stripe rescue list. Dedup by invoice ID.

**Off-Stripe rescue list** (pay by check/ACH, sit past-due in Stripe, never marked paid there): Tejas Brewery, Giant Texas, Tejas Beer, Oceanbox. Their invoices live in Stripe with full line-item detail, so read splits directly. Crust and Holland also pay by check but ARE marked paid in Stripe, so they appear in normal paid pulls; do NOT add them via the rescue list or they double count. Sweep monthly for any new finalized-but-unpaid invoice that was actually collected.

**MRR** = subscription line items, recognized by subscription period month.
**One-off** = all manual invoice items, a separate line, even when the service looks recurring. (A manual "Meta Advertising" charge is a billing-hygiene flag, not MRR.)
**Exclude** line items whose description is "Ad Spend Reimbursement" (pass-through, not revenue, no margin).

**Normalization:** strip the leading "N x " quantity prefix and the trailing "(at $X / period)" suffix, then map.

**Service-to-team map:** Meta Advertising and TikTok Advertising to Meta; Google Advertising to Google; Email Marketing and SMS Marketing to Email; Organic Social, Social Media Management, and Content Creation to Social; Website Development to Web; Creative Package to Creative; SEO to SEO; CRM and CRM Maintenance to GHL.

Assert the engine against `mrr_by_team_month_stripe` and `oneoff_total_by_month_stripe` in the fixtures.

---

## Labor engine (validated composition)

Labor = Gusto actuals allocated by Toggl hours (salaried flat, hourly as hours times rate), reconciled to Gusto.

- **Meta** carries media buyers ONLY (Mark A., Dipesh, Thomas, Gustavo, Eduarda, Arthur, Priscila, plus Camille on copy). May labor 13,768.
- **Creative** carries designers and video editors (Nelson, Hillary, Jazem, Teuta, Mira, Daniel) PLUS photographers from Xero Contractors (Jonathan Quiroz, Tanner Walsh, billed per shoot). May labor 7,982 (7,622 staff + 360 Quiroz).
- **Google** Sultan, Aneesa, Salman. **Social** Peter, Camila. **Email** Mel, Eunhye, Adriana, Andres, Dani Beltran, Niro, Facundo, Lawrence, Renato, Fernando. **Web** Jesus, Lubin, Andrew, Francisco, Andres G. **GHL** Clare plus Kennedy (ramping). **SEO** no dedicated staff; labor embedded in Google. **Operations** (company overhead, not a delivery team) Fabi, Jorgi.
- Removed from prior rosters and must not appear: Nomaan, Waseem, Isaly, Angel, Rafael, Del.

Full roster with rates is in the prototype and the fixtures (`per_team_may`).

**Key finding to preserve:** splitting labor cleanly makes Meta read about 69% margin, but Creative, GHL, and Web read negative on recurring revenue alone, because their output is embedded in Meta retainers and one-off builds. This is intended true-margin visibility, not an error.

---

## Software and overhead

Apply the allocation key (separate doc). Per-team monthly software totals and product breakdown are in the fixtures (`software_breakdown_monthly`). Claude and Slack split by seat at $49.75/seat/month. Operations, Sales/outreach, and Misc stay at company level. Diiiploy $6,666 is a one-time OS build, excluded from run-rate. Remitly reclassed to labor. Klaviyo nets negative (reimbursements and referral income).

---

## Margin model

- Per team: MRR minus labor minus allocated software (contribution margin).
- Per client: revenue (real) minus cost. **Per-client cost requires Toggl.** Until then, the prototype uses modeled placeholder factors (`cost_factors_PLACEHOLDER`); these must NOT ship as real. Replace with Toggl-derived per-client labor.
- Company: total MRR plus true one-off, minus all labor, minus all software, minus overhead. Reconcile to Xero cash as a secondary lens; surface the residual.

---

## Dashboard surface (six tabs, matches prototype)

1. **Company Health:** five metrics, each with month-over-month and year-over-year (Total revenue from Xero as source of truth, Total MRR, Average ticket value, Average subscriber lifetime, Company margin). Total profit card with month-over-month. Revenue two-lens reconciliation. Revenue and profit MoM are real from the Atlas; MRR-level MoM needs prior-month MRR; lifetime needs Stripe subscription history; YoY needs last year.
2. **Per Team:** contribution margin table. Hover MRR for top 5 clients on that service (real), Labor for the employee breakdown (Toggl), Software for the product list (real, from the key).
3. **Per Client:** every client, sorted lowest margin first. Columns revenue, cost, margin, margin %. Hover cost for team and employee breakdown. Cost modeled until Toggl.
4. **Employees:** roster with team and pay rate, salary/hourly/contractor tagged.
5. **Pulse:** top 5 most profitable and top 5 least profitable clients (hover for revenue and cost); service-line cost ranked (hover for employee breakdown, MoM activates with history); biggest Xero cost increases vs last month (hover for itemized transactions, real).
6. **Projection:** projected month revenue, MRR vs last month, average ticket vs last month, pace, six-month trend. Needs history to be real.

**Source badges throughout** so validated, modeled, and pending data are never confused: Stripe, Xero, Key, Atlas, Model.

**Brand tokens** (match exactly): red #B21E2C (use #D93B47 on dark), black #060606, off-whites #F2F2F2 and #FAFAFA. Fonts: GT Flexa for display (Familjen Grotesk is the free stand-in), Poppins for body. Corner radius 5px. Lowercase "kaizen" wordmark. Dark mode is the default.

---

## Refresh and delivery

Daily job pulls all four sources, recomputes, and writes a dated snapshot so MoM and projection have history. Monthly Asana task via Cowork: weekly Monday trigger with an "only run if second Monday" conditional, posts the formal review.

---

## Build phases and acceptance

1. **Revenue engine.** Assert per-team MRR and one-off against the fixtures for all five months. Done when the numbers match.
2. **Labor engine.** Toggl plus Gusto, reconciled to Gusto totals and to Xero account 830.
3. **Software and overhead.** Apply the key; per-team totals match the fixtures.
4. **Margin model.** Per team, per client, company; total profit and margin match May validated figures.
5. **Dashboard UI and daily refresh.** Six tabs against the prototype; snapshots writing.
6. **Monthly Asana task** via Cowork.

---

## Open items that need live connection (not rework, just pending inputs)

- Toggl wired in turns per-client cost, employee drivers, and hourly labor real.
- Confirm Oceanbox's subscription split from its Stripe invoice (currently assumed all Email).
- Add Kennedy's hours to GHL once in Gusto.
- Backfill subscriber start and cancel dates from Stripe for average subscriber lifetime.
- Load prior year for year-over-year.

---

## Reconciliation reality (do not chase a false tie)

Monthly cash does not reconcile cleanly to the Atlas across all months, and that is expected. One-off project revenue is lumpy (March had $37,650 of builds versus $11,325 in May) and checks arrive bunched. MRR recognized by period is the stable, comparable decision metric. Cash is the secondary reconciliation lens, with the residual surfaced rather than forced.
