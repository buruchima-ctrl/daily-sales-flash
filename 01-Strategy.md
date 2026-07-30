# Daily Sales Flash — Strategy
**Author:** Strategy layer (Claude Fable) · **Builder:** Opus · **Date:** 2026-07-24 · **Status:** Approved v1.1 — Barma approved all §7 defaults 2026-07-24; foundation phase built and green, renderer phase pending checkpoint

---

## 1. Context

Every retailer produces a daily sales flash. Almost none produce a good one. The typical version is an analyst pulling numbers at 7am into a spreadsheet, pasting into an email, and hoping the formulas held — no calendar alignment, no narrative, no disclosure of which stores haven't posted yet. The Fortune-500s get a proper flash as a byproduct of a seven-figure BI stack; the mid-market gets Excel.

This is the purest expression of the portfolio thesis: **give retailers and brands a tool they need daily but almost never have in house.** It is also the wedge product — the flash puts the system's name in front of an executive every single morning, at near-zero marginal cost, and builds the daily habit that makes every other engagement natural.

The flash is not a seventh lifecycle stage. It is the **operating rhythm across all of them**: daily flash → weekly trade recap → monthly scorecard (Supply Chain) → quarterly committee (Door Engine).

## 2. Thesis

A flash succeeds on three things, in this order: **it arrives every morning without fail; the numbers are calendar-true; it says why, not just what.** Metric count is not a success factor — a flash with forty tiles is a dashboard nobody asked for. The product is a *narrative with receipts*, delivered where executives already are (inbox, phone, Slack), never a destination they must remember to visit.

## 3. Strategic goals

| # | Goal | North-star measure | Direction |
|---|------|--------------------|-----------|
| G1 | The morning number is trusted | Restatements after first send | → 0 |
| G2 | Comparisons are calendar-true | % of comps day-aligned to the retail calendar (incl. holiday shifts) | 100% |
| G3 | The flash explains itself | Every headline miss/beat carries a decomposed "why" | 100% |
| G4 | Immature data never misleads | Late posters and unsettled e-comm always disclosed, never silently mixed | 100% |
| G5 | Zero manual work | Analyst minutes per daily flash | 0 |

## 4. Strategic pillars

### Pillar 1 — Calendar truth is the moat
"Yesterday vs the same date last year" is wrong most days of the year. The comparison is *same fiscal week, same day of week*, on a retail 4-5-4 calendar, with floating holidays mapped explicitly (Easter, July 4, Thanksgiving/Black Friday, Christmas Eve's day-of-week) and 53rd-week years restated. This is the hard part every spreadsheet flash gets wrong — and the portfolio has already solved the class of problem once (the Door Engine's 4-4-5 calendar with 53-week handling). Port the discipline, not necessarily the code.

### Pillar 2 — Exception-first, three things not forty
The flash leads with the headline (total, comp, plan attainment) and then names at most three adverse movers and one bright spot, each with a plain-English reason decomposed to channel / region / store. Same adverse-movers-only discipline as the Supply Chain variance engine, at daily grain.

### Pillar 3 — Honest about immature data
Yesterday's e-comm has unshipped orders and unrecorded returns; some stores post late. The classic flash credibility-killer is quietly mixing settled and unsettled numbers. Every flash carries a completeness banner (stores reported, % of expected sales posted) and e-comm demand vs shipped shown as what they are. The Supply Chain build's settled-data-lag concept applies here at day grain.

### Pillar 4 — Delivered, not visited
One compute renders to every surface: an email-ready HTML flash (phone-first), a Slack-pasteable text block, a printable one-pager, and a web archive for the trailing history. If the exec has to click through to a dashboard, the product has failed.

### Pillar 5 — The flash is a data spine, not just a report
The daily fact table the flash runs on (sales × store × channel × day, plan, calendar) is the foundation the promo/markdown-effectiveness marketing tool consumes next. Build the spine once, correctly, and the marketing tool becomes its second reader — the platform story starts here.

## 5. Operating cadence the product creates

| Cadence | Artifact | Audience |
|---------|----------|----------|
| Daily 07:00 | The flash (email/Slack/print) | Everyone — CEO to planners |
| Monday | Weekly trade recap edition (week just closed, WTD plan for the new week) | Trade meeting |
| Period end | Hand-off row to the monthly scorecard (Supply Chain system) | Leadership |

## 6. Decision rights (what the flash triggers)

- **Comp negative two consecutive days in a channel/region** → named in the flash's focus panel with decomposition; trade meeting agenda item auto-suggested.
- **A store unreported by send time two days running** → escalation flag to ops on the flash itself.
- **Plan attainment < threshold at WTD mid-week** → the Monday recap proposes the gap-to-go required run-rate for the back half.
- **Holiday-shift week** → the flash automatically states both raw and shift-adjusted comps; the adjusted number leads.

## 7. Owner decisions — **all approved as recommended (Barma, 2026-07-24)**

| # | Decision | Approved choice | Alternative (not taken) |
|---|----------|-----------------|-------------------------|
| D1 | Retail calendar | **NRF 4-5-4, fiscal year starting the Sunday nearest Feb 1** — the industry standard a client would expect | 4-4-5 July–June (Door Engine convention) |
| D2 | Demo retailer | **Reuse Lumière Beauty Co.** — same 25 stores as the Lease Toolkit (`Leases/src/roster.py`) plus an e-commerce channel; one fictional company across products is the platform story. Roster gaps (remodel/close dates, sales bands) synthesized deterministically. | New fictional retailer |
| D3 | Channels v1 | **Stores + e-commerce** | Add wholesale/marketplace later |
| D4 | Delivery surfaces v1 | **Email HTML + web archive + print; Slack text block included (it's cheap)** | Email only |
| D5 | Traffic/conversion | **Exclude v1, schema-ready** — most mid-market clients lack reliable traffic feeds; don't let a missing feed break the habit product | Include as optional feed |

Delivery approach (also approved): **foundation-first with an owner checkpoint** between the data/calendar/catalog foundation and the compute/render phase.

## 8. Success definition (for the demo build)

1. Sixty days of daily flashes generate from seeded data with zero manual steps; "today's" flash generates on demand.
2. Every comp in every flash is day-aligned per D1, verified by acceptance test against hand-computed cases, including one holiday-shift week.
3. The focus panel's reasons reconcile: named drivers sum to the headline gap they explain.
4. A CFO reading five consecutive flashes finds zero arithmetic surprises and zero undisclosed data gaps.
5. The email rendering passes the phone test: readable on a 375px screen, no horizontal scroll, no external assets.
