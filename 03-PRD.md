# Daily Sales Flash — Product Requirements Document (PRD)
**Author:** Strategy layer (Claude Fable) · **Builder:** Opus · **Date:** 2026-07-24 · **Status:** Approved v1.1 — Strategy §7 and §11 defaults approved by Barma 2026-07-24. **Build status:** foundation complete and green (`flash/calendar.py`, `flash/catalog.py`, `schema.sql`, `seed.py`, `run_flash.py --check`, tests); remaining: `compute.py`, `focus.py`, `narrative.py`, four renderers, `app.py`, restatement generation, `README.md`
**Reading order:** `01-Strategy.md` (intent) → `02-BRD.md` (rules) → this document (what to build). Where this PRD is silent, choose the simplest option consistent with the BRD's business rules and note the choice in your build summary.

---

## 1. Product overview

A generator that turns a daily sales fact table into a **send-ready morning flash**: one computed object per day, rendered to four surfaces (email HTML, Slack text, print one-pager, web archive). Python 3 standard library only + SQLite (the Supply Chain stack — proven, nothing to install). No server required to *generate*; a stdlib `http.server` app serves the archive for browsing.

```
seed.py → flash.db → compute.py (metric catalog, per day) → render/
                                   ├─ email/2026-07-23.html      (inline CSS, phone-first)
                                   ├─ slack/2026-07-23.txt       (paste-ready block)
                                   ├─ print/2026-07-23.html      (@media print one-pager)
                                   └─ site/ (archive: index + per-day pages + calendar nav)
app.py → serves site/ + "generate today" endpoint
```

## 2. Deliverables & layout

All under `/Users/barmauruchima/Documents/Claude/Projects/Sales Flash/`:

| Path | What it is |
|------|-----------|
| `flash/calendar.py` | NRF 4-5-4 calendar: fiscal year/period/week/day mapping, day-aligned LY resolution, holiday map, 53-week restatement |
| `flash/catalog.py` | The metric catalog (§5) — the only place formulas live (BR-5) |
| `flash/compute.py` | Builds the per-day flash object: headline, slices, focus panel, completeness, narrative |
| `flash/focus.py` | Adverse-mover ranking + driver decomposition (§6) |
| `flash/narrative.py` | Deterministic template composition of the summary paragraph (no LLM) |
| `flash/render_email.py` / `render_slack.py` / `render_print.py` / `render_site.py` | The four surfaces, all consuming the same computed object |
| `seed.py` | Seeded generator: roster, calendar, 2+ years of daily facts, plan, planted storylines (§7); asserts every consistency rule |
| `app.py` | stdlib server: archive browsing + generate-on-demand |
| `schema.sql`, `flash.db` | SQLite schema + seeded database |
| `run_flash.py` | CLI: `--date YYYY-MM-DD` (default: latest complete day), `--all` (regenerate the archive), `--check` (asserts only) |
| `README.md` | Build summary: how to run, conventions, deviations, planted storylines and where to see them |

## 3. Data model (SQLite)

- `stores` — ported from `Leases/src/roster.py` (D2): store_number, name, region (5 US regions), open_date, close_date NULL, remodel ranges (from the lease roster's remodel pipeline), comp_eligible derived per BR-2. Plus one virtual `ECOM` channel entity.
- `calendar` — one row per calendar date: fiscal_year, period (1–12), week (1–52/53), day_of_week (1=Sun), holiday_code NULL, ly_aligned_date (materialized per §4), restated flag.
- `sales_day` — date × store (or ECOM) grain: net_sales, transactions, units. For ECOM additionally: demand_sales, shipped_sales, returns_recorded. Posted_at timestamp (drives completeness + late-poster logic).
- `plan_day` — same grain: plan_sales (annual plan spread by period weight × day-of-week curve; the seed generates it).
- `flash_archive` — one row per generated flash: date, version, computed object (JSON), created_at. Immutable per BR-7; restatements append version+1 with a reason string.

## 4. Calendar spec (the moat — build this first, test it hardest)

1. **NRF 4-5-4**: fiscal year starts the Sunday nearest Feb 1; periods grouped 4-5-4 per quarter; 53rd week added when needed. **Corrected during build:** the 53-week years under this rule are FY2023, FY2028, and FY2034 (the draft's FY2029 guess was wrong). None falls in the archive's comp path (FY2026 vs FY2025), so 53-week/restated-shift logic is verified by synthetic unit test, which §10 explicitly permits.
2. **Day-aligned LY** (BR-1): LY counterpart = same fiscal week number, same day-of-week, from the prior fiscal year. In 53-week years use the NRF restated shift (BR-8).
3. **Holiday map**: explicit table of floating holidays — Easter, Mother's Day, Memorial Day, July 4 (fixed date, floating weekday), Labor Day, Thanksgiving + Black Friday + Cyber Monday, Christmas Eve/Day, New Year's Eve/Day, Valentine's Day (fixed date, floating weekday). For a date carrying a holiday_code, the LY counterpart is **the same holiday_code's date last year**, overriding week/day alignment; the flash states when a holiday override is in effect and shows raw + adjusted comps (Strategy §6).
4. **Materialize** `ly_aligned_date` into the calendar table at seed time so every downstream comp is a join, not a computation — one place to be right (BR-5 applied to dates).
5. Port the *discipline* of `Portfolio Analysis/engine/` calendar code (label parsing that rejects ambiguity, boundary tests, 53-week years asserted by test) — the Door Engine's calendar is 4-4-5 July-start, so the code itself does not transplant directly. Its bug list is required reading: `parse_label` accepting calendar months and `period(fy, 0)` negative-indexing are the exact classes of defect to test against here.

## 5. Metric catalog (formula card style; ◆ = appears in the headline row)

| # | Metric | Formula | Notes |
|---|--------|---------|-------|
| 1◆ | Net Sales (day) | Σ net_sales over reported entities | Stores + ECOM demand (labeled, BR-4) |
| 2◆ | Comp Sales % (day) | (comp-store TY ÷ comp-store LY-aligned) − 1 | BR-1/BR-2; raw-date comp computed but never leads |
| 3◆ | Plan Attainment % (day) | actual ÷ plan_day | |
| 4 | WTD / MTD(period) / YTD Net Sales | Σ over fiscal window to date | Same three comparisons as day grain |
| 5 | WTD / MTD / YTD Comp % | window TY ÷ window LY-aligned − 1 | Windows built from aligned days, not shifted totals |
| 6 | WTD / MTD / YTD Plan Attainment | Σ actual ÷ Σ plan | |
| 7 | Transactions (day, vs LY) | count; comp basis same as #2 | |
| 8 | AOV | net_sales ÷ transactions | |
| 9 | UPT | units ÷ transactions | |
| 10 | AUR | net_sales ÷ units | |
| 11 | E-comm Demand vs Shipped | both sums, day grain | Demand leads day-of; shipped/settled shown as maturing (BR-4) |
| 12 | E-comm Settled Return Rate | returns ÷ shipped, matured window only | Never computed on immature days |
| 13 | Completeness % | reported stores ÷ expected; posted sales ÷ trailing-4-same-weekday average | Powers the banner (BR-3) |
| 14 | Gap-to-Go Run Rate (Monday recap) | (WTD/period plan remaining) ÷ selling days remaining | Recap edition only |
| 15 | Contribution to Comp Gap | entity (TY − LY-aligned) ÷ total LY-aligned | The focus panel's decomposition unit (BR-6) |

Every rendered metric card/row carries its formula on hover (web) or in the footer key (email/print) — the Supply Chain formula-card pattern.

## 6. Focus panel (the "why")

1. Compute #15 for every channel, region, and comp store for the day and WTD.
2. Rank **adverse** contributors (sign against the headline); pick up to 3, plus the largest favorable one ("bright spot").
3. Prefer the highest level that explains the movement: if one region explains >60% of the gap, name the region and its worst two stores inside it, not ten stores.
4. Each entry renders as one plain-English line with receipts: *"Southeast −$41.2K vs LY (−7.9%) — Palmetto Landing and Copper Row drove two-thirds of it; region was the only negative-comp region."*
5. Reconciliation (BR-6): displayed contributions + "all other" remainder = headline gap exactly; an assertion, not a hope.
6. Late-poster escalation (BR-3): a store missing at generation time two consecutive days appears in the panel regardless of rank.

## 7. Seeded demo data (deterministic, storylines planted)

Seeded RNG (fixed seed), 2 full fiscal years + current-year-to-date so every comp window resolves. Base curves: per-store annual volume from the Lumière lease roster's sales bands; period seasonality (holiday-weighted Q4); day-of-week curve (Sat peak, Tue trough); e-comm ~22% of revenue, faster growth than stores.

**Planted storylines — the acceptance material.** The seed must create, and `README.md` must index, at least:
1. A **holiday-shift week** in the current period (July 4 weekday shift) where raw and adjusted comps differ visibly.
2. A **soft region** (Southeast) driven by two specific stores over the trailing two weeks — the focus panel must find and decompose it.
3. A **remodel closure** (use a store the lease roster marks overdue-for-remodel, e.g. LB-013) with comp exclusion and footer disclosure (BR-2).
4. A **late-poster incident**: two stores unposted on one recent day (completeness banner), one of them for a second consecutive day (escalation).
5. An **e-comm maturation case**: a recent day whose demand looked −8% but settles positive once shipped catches up — visible by comparing that day's flash to the archive's settled view (BR-4, no silent rewrite).
6. A **new store** (opened < 13 periods ago) visibly excluded from comp but included in total (BR-2).
7. One **plan-beat bright spot** store for the favorable slot.
8. A generated flash **restatement** (version 2) for one archive day, with its reason string rendered (BR-7).
`seed.py` asserts each storyline actually manifests in the data (the Lease Toolkit's assertions-not-hope standard).

**As-built storyline assignments** (constants in `seed.py`; the render phase must surface exactly these):

| Storyline | Assignment |
|-----------|-----------|
| Anchors | "Today" fixed at **2026-07-24**; latest complete day **2026-07-23** (never `now()`, NFR-2) |
| 1. Holiday shift | July 4 weekday shift, current period |
| 2. Soft Southeast | **LB-009 + LB-010** from 2026-07-10, ×0.78. (The §6.4 example line naming "Copper Row" is illustrative — LB-014 is actually Midwest.) |
| 3. Remodel closure | **LB-013** (Lakeview Arcade), remodel start 2026-06-15, no rows from that date |
| 4. Late posters | **LB-021** missing 07-22 **and** 07-23 (escalates); **LB-005** missing 07-23 only |
| 5. ECOM maturation | **2026-07-23**: demand −8% vs LY, settles +5% shipped |
| 6. New non-comp store | **LB-025** (opened 2025-08-01, < 13 periods) |
| 7. Bright spot | **LB-022** (Pacific Heights Court, West), ×1.18 from 2026-07-17 |
| 8. Restatement | **2026-07-20** re-issued as version 2 (generated in the render phase, not the seed) |

## 8. Render surfaces (one compute, four faces)

- **Email** (`render_email.py`): single HTML file per day, inline CSS only, no external assets, no JS, ≤100KB, table-based layout that survives email clients, readable at 375px. Subject-line convention in a comment: `Flash — Wed Jul 23 · $412K · comp +2.1% · plan 98%`. Dark-mode-safe colors.
- **Slack** (`render_slack.py`): plain-text block with the headline row, three focus lines, completeness line. No markdown exotica; paste-ready.
- **Print** (`render_print.py`): one page, `@media print`, the trade-meeting handout.
- **Web archive** (`render_site.py` + `app.py`): index with calendar navigation (fiscal weeks, not calendar months), per-day pages, the settled-vs-flash view for BR-4 days, restatement history for BR-7. Design language: the portfolio's tokens (gold input / blue presentation / green calculated, Avenir/Charter/mono stacks) — see `Portfolio/HANDOFF - Portfolio Presentation.md` §3. Include `<meta charset="utf-8">` in every generated HTML file (the Lease review's deploy note — do not repeat that defect).

## 9. NFRs

- **NFR-1** Python 3.9+ stdlib + SQLite only; zero pip installs; runs offline.
- **NFR-2** Deterministic: same seed → byte-identical `flash.db` CSV exports and byte-identical rendered files (timestamps come from the data, never `now()` — also required for the reviewer's regeneration diff).
- **NFR-3** Full 60-day archive regeneration < 30 seconds on a laptop.
- **NFR-4** Every assertion failure names the storyline/rule it guards, the offending rows, and what to fix.
- **NFR-5** Charset declared in all HTML; email file passes a no-external-request check (grep: no `http` src/href except the archive's internal links).

## 10. Acceptance checklist (the reviewer will re-derive independently)

- [ ] `seed.py` then `run_flash.py --all` completes with zero manual steps; rerun reproduces byte-identical outputs (NFR-2).
- [ ] Hand-check day comp % (#2) for one ordinary day against direct SQL: comp-store set correct (new store out, remodel days out), LY dates aligned per §4.
- [ ] The holiday-shift storyline: raw ≠ adjusted, adjusted leads, override noted in the flash.
- [ ] Focus panel reconciliation (BR-6) asserts to the cent on every generated day; spot-verify the Southeast storyline decomposition.
- [ ] Late-poster day: totals exclude missing stores, banner discloses, second-day store escalates (BR-3).
- [ ] E-comm maturation day: flash version unchanged, settled view differs, both visible in the archive (BR-4, BR-7).
- [ ] Restated day renders version history with reason (BR-7).
- [ ] Email file: ≤100KB, inline CSS, no external assets, renders on a 375px viewport without horizontal scroll.
- [ ] All four surfaces agree on every number for three sampled days (BR-5).
- [ ] 53-week handling: the calendar materialization is asserted by test for the seed range; restated-shift comp verified on at least one synthetic case (unit test is sufficient if no 53-week year falls in the archive window).

## 11. Open questions — **defaults approved as written (Barma, 2026-07-24)**

| Q | Default |
|---|---------|
| Timezone handling for "yesterday" | Single business timezone (America/New_York); no per-store TZ in v1 |
| Plan granularity | Annual plan → period weights → day-of-week spread, generated by seed; no re-planning mid-year in v1 |
| Comp definition edge (ECOM) | ECOM is always comp (it has 2 years' history in the seed); flag in footer that ECOM comp is demand-based day-of |
| Narrative tone | Factual, ≤ 3 sentences, numbers inline; reads like the focus panel, not like marketing |
| Archive depth in demo | 60 generated days + on-demand "today" |
