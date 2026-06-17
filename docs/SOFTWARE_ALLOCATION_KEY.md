# Kaizen Software Allocation Key

**Purpose:** Maps the Xero "Softwares" account to teams so the P&L dashboard can compute true margin per team.
**Basis:** Cash basis. Source: Xero Account Transactions, account 835 (Softwares), Jan 1 to May 31, 2026.
**Account total over period:** $48,572.34 (about $9,714/mo, of which roughly $8,381/mo recurring + a one-time item).
**Rule:** Tools tied to one team's delivery load into that team. Cross-cutting and non-delivery costs stay at company level and do not touch team margins.

---

## Team-attributable software (loads into team margin)

| Team | Seats | Claude+Slack seat share /mo | Direct tools /mo | Total /mo |
|---|---|---|---|---|
| Meta (incl. creative) | 9 | $448 | $750 | $1,198 |
| Creative | 3 | $149 | $739 | $888 |
| Email | 7 | $348 | $337 | $685 |
| Web | 3 | $149 | $224 | $373 |
| Google | 2 | $99 | $261 | $360 |
| SEO | 0 | $0 | $195 | $195 |
| GHL | 0 | $0 | $136 | $136 |
| Organic Social | 1 | $50 | $0 | $50 |

Direct-tool detail per team:

- **Meta:** Deal.ai (100%), Motion (50%), Supermetrics (50%)
- **Creative:** Canva, Adobe, Freepik, Envato, Arcads, Higgsfield, Magnific, Hedra, ElevenLabs, Motion (50%)
- **Email:** Figma, EmailLove
- **Web:** GoDaddy, Hostinger, FastComet, Elementor, WP All Import, WordPress
- **Google:** Spyfu, Supermetrics (50%)
- **SEO:** Conversion (Seona.ai)
- **GHL:** GoHighLevel
- **Organic Social:** no dedicated tools; seat share only

---

## Company-level buckets (do NOT touch team margin)

| Bucket | Per month | Contents |
|---|---|---|
| Operations | ~$2,906 | OS dev stack (Cursor, Base44, Supabase, Vercel, Mem0, Embedchain, Brainless Lab, Cloudflare), cross-cutting tools (ChatGPT, Zoom, Toggl, Notion, Calendly, Loom, Google Workspace, Microsoft, Grammarly, Fireflies, Zapier, Make, Xero), plus the 4 company seats' share of Claude+Slack |
| Sales / outreach | ~$1,216 | Riverside (podcast video), internal Klaviyo (net of reimbursement + referral credits), Instantly, internal GHL instance (22 Apps), Referral Partner Academy |
| Misc | ~$103 | Spotify, Surf Shark, Buzzsprout, Paddle, Internet.game, Volley, Click Funnels, Bullzeye |
| One-time (non-recurring) | $6,666 total | Diiiploy AI, original OS build, fully paid, drops off going forward |

Reclassified out of software entirely:
- **Remitly** (~$271/mo) moves to contractor/labor cost, it is a payment rail, not a tool.

---

## Splits and methods

- **Motion:** 50% Meta, 50% Creative
- **Supermetrics:** 50% Meta, 50% Google
- **Claude + Slack:** allocated by seat count. Pool ~$1,443/mo across 29 seats = $49.75/seat/mo. One members export currently drives both Claude and Slack; supply a separate Slack export if its seat distribution differs.

Seat counts by team: Meta 9, Email 7, Creative 3, Web 3, Google 2, Social 1, plus 4 company seats (Santi, Kyle, Ryan, Jorgi) whose share stays in Operations.

---

## Assumptions and open notes

- **Klaviyo nets negative** in this account because of a campaign reimbursement and referral fees Klaviyo pays Kaizen. The internal Klaviyo cost is treated as Sales/outreach, not Email-team delivery. Client Klaviyo billing lands outside this account (client cards / direct), so it is not a Kaizen cost here.
- The Klaviyo **referral fees are really income**; consider tracking them as revenue rather than a software credit in a future pass.
- **Salaried wages are absent from cash-basis Xero** (booked as journals). Labor for the dashboard comes from Gusto actuals allocated by Toggl, never from the Xero wages line.
- This key should be revisited only when software is added or dropped, or when seat counts change.
