# Kaizen Profit & Loss Dashboard: Build Spec

## Purpose and guiding principle

A daily-refreshing internal dashboard showing true profit and loss per team, per client, and company-wide, decoupled from cash-timing noise. Decisions run off MRR. Cash is kept only to reconcile back to the books and the CPA-reconciled total. Validated end to end against real May 2026 data before any code was written.

---

## Architecture at a glance

- Lives as a Claude Code app in the kaizen-cc org, alongside Kaizen Launch.
- Pulls four sources: Stripe (revenue), Gusto (labor actuals), Toggl (labor allocation), Xero (overhead, software key, cash reconciliation).
- Runs a daily refresh and writes a dated snapshot so month-over-month and projection math has history.
- Serves a five-tab dashboard. A Cowork scheduled task posts the monthly review to Asana on the second Monday.
- Two revenue lenses: MRR (the decision metric) and cash collected (book reconciliation only).

---

## Data sources and ingestion

### Stripe (revenue)
- Pull all finalized invoices with line items.
- Revenue rule: count an invoice if status is paid OR the customer is on the off-Stripe rescue list. Dedup by invoice ID so check-payers already marked paid (Crust, Holland) are never counted twice.
- MRR: subscription line items (parent.subscription_item_details), recognized by the subscription period month, NOT by payment date. This is what neutralizes late and multi-month catch-up checks.
- One-off: all manual line items (parent.invoice_item_details), kept as a fully separate line regardless of whether the service looks recurring.
- Normalization: strip the "N x " prefix and the "(at $X / period)" suffix from descriptions. Amounts are in cents.
- Service-to-team map applies after normalization. TikTok goes to Meta, SMS goes to Email, Content Creation goes to Social.

### Off-Stripe rescue list
Clients who pay by check or ACH and may sit past-due in Stripe: Crust, Holland Law, Tejas Brewery, Giant Texas, Tejas Beer, Oceanbox. Their invoices live in Stripe with full line-item detail, so no manual splits are needed. The daily job sweeps for any other finalized-but-unpaid invoice that was actually collected, to keep this list honest.

### Toggl (labor allocation)
- Reports API, requires an API token from the Toggl profile. This is what makes the daily refresh hands-free.
- Hours per member, per client, per month. Used to distribute labor dollars across teams and clients.

### Gusto (labor actuals, source of truth)
- Actual payroll: salaried staff (flat monthly) and contractors (hourly).
- Labor always comes from Gusto, never from Xero, because cash-basis Xero drops salaried wages (booked as journals).
- Toggl hours allocate Gusto labor to teams and clients. Totals reconcile back to Gusto each run.

### Xero (overhead, software, reconciliation)
- Cash basis.
- The locked software allocation key assigns the Softwares account to teams (direct tools plus the Claude and Slack seat share). Operations, Sales, and Misc stay at company level.
- Remitly is reclassed to labor. The one-time Diiiploy OS build is excluded from the monthly run rate.
- Xero cash P&L and the CPA-reconciled total are used to tie the company number and surface any residual.

---

## Calculation model

### Per team, monthly
- Revenue: MRR from active subscriptions, period-recognized. One-off shown separately.
- Labor: Gusto actuals allocated by Toggl (salaried flat, hourly as hours times rate), reconciled to Gusto.
- Software: direct team tools plus Claude and Slack seat share, from the allocation key.
- Contribution margin: MRR minus labor minus software.

### Company-wide
- Net profit: total MRR plus true one-off, minus all labor, minus all software (including Operations, Sales, Misc), minus overhead.
- Reconcile to Xero cash and the CPA truth. Surface the residual rather than forcing a match.
- Owner split 33/33/33 off net profit, with tax brackets (22 / 22 / 24).

### Per client
- Revenue (MRR plus one-off), labor (Toggl hours times rate), margin, loss-maker flag, days since onboard.

---

## Dashboard tabs

1. Company Health: true P&L, MRR versus last month, net margin, cash-versus-MRR reconciliation, owner split.
2. Per Team: MRR, labor, software, contribution margin, month-over-month deltas, automatic flags when a margin drops past a set threshold.
3. Per Client: revenue, labor, margin, loss-makers, days since onboard.
4. Pulse: cost composition and what moved month over month (for example, Email cost up driven by new hires, Meta-versus-Email cost mix shift), biggest drivers ranked, plus billing-hygiene flags (the manual-but-recurring conversion list and any past-due off-Stripe invoices).
5. Projection: projected month revenue (contracted MRR remaining plus a one-off run-rate estimate), MRR versus last month, average ticket versus last month, pace versus prior month.

---

## Refresh and delivery

- Daily job pulls all four sources, recomputes the full model, and writes a dated snapshot. Snapshots power month-over-month and projection and are retained as the historical baseline.
- Monthly Asana task: a Cowork scheduled task on a weekly Monday trigger with an "only run if today is the second Monday" conditional. It builds the formal monthly review and creates an Asana task assigned to Santi with the report attached.

---

## Reference data the build consumes

- Software allocation key (already delivered).
- Service-to-team classifier and normalization rules.
- Off-Stripe rescue list.
- Claude and Slack seat counts per team.
- Employee roster: name to team to rate (salaried flat or hourly).
- MRR period-recognition rule and off-Stripe period-bucketing convention.

---

## Open items before and during build

- Toggl Reports API token (the one true prerequisite for a hands-free daily refresh).
- Gusto reconciliation pass to confirm labor ties to the roster figures.
- Confirm Oceanbox's subscription split in Stripe, run the off-Stripe sweep, and close the roughly $3,100 May residual against the $139,425 CPA total.
- Decide whether the manual-but-recurring items get a labeled flag versus just appearing in the one-off bucket (currently: appear in one-off, flagged in Pulse).
- Backfill January through May and validate the whole model against the Atlas before going live.

---

## Build phases

1. Revenue engine (Stripe plus off-Stripe rescue), validated January through May against the Atlas and CPA.
2. Labor engine (Gusto plus Toggl), reconciled to actuals.
3. Software and overhead (Xero allocation key).
4. Margin model, company P&L, owner split.
5. Dashboard UI (five tabs), daily refresh, snapshot storage.
6. Monthly Asana task via Cowork.
